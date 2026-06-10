"""Core Vertex AI-powered SQLite text-to-SQL agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
import re
import time
import unicodedata

from .config import (
    DEFAULT_DB_PATH,
    DEFAULT_MAX_ROUNDS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_RESULT_LIMIT,
    DEFAULT_SCHEMA_SAMPLE_ROWS,
    DEFAULT_TEMPERATURE,
    DEFAULT_VERTEX_LOCATION,
    DEFAULT_VERTEX_PROJECT,
)
from .schema import SchemaInspector
from .sqlite_tool import execute_sqlite_sql
from .vertex_client import VertexAIClient


TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
FUNC_RE = re.compile(r"<function=([^>]+)>")
PARAM_RE = re.compile(r"<parameter=([^>]+)>(.*?)</parameter>", re.DOTALL)


SYSTEM_PROMPT = """\
You are a careful text-to-SQL agent for a local SQLite database.

Goal:
- Understand the user's question and the provided SQLite schema.
- Generate SQLite SELECT/WITH queries.
- Execute queries using execute_sql.
- Inspect results and refine until the query and answer are correct.
- Finish with terminate, providing both final SQL and a concise answer.

Rules:
- Only produce SQLite SELECT/WITH queries.
- Never modify data.
- The final answer must be grounded in a successful query result.
- The final answer must include the concrete values needed to answer the question; do not say only that results were calculated or displayed.
- Answer in the same language as the user's question when possible.

Tools:

<function>
<name>execute_sql</name>
<description>Run one read-only SQLite SELECT/WITH query and inspect preview rows.</description>
<parameters>
<parameter>
<name>sql</name><type>string</type><required>true</required>
</parameter>
</parameters>
</function>

<function>
<name>terminate</name>
<description>Submit final SQL and natural-language answer.</description>
<parameters>
<parameter>
<name>sql</name><type>string</type><required>true</required>
</parameter>
<parameter>
<name>answer</name><type>string</type><required>true</required>
</parameter>
</parameters>
</function>

When calling a tool, output exactly this XML-like format:

<tool_call>
<function=FUNCTION_NAME>
<parameter=PARAM_NAME>
VALUE
</parameter>
</function>
</tool_call>

Important:
- Output exactly one tool_call per turn.
- You may write a short reason before the tool_call block, but write nothing after it.
- After a successful execute_sql result that answers the question, call terminate immediately with the exact successful SQL and a concise answer.
- When terminating, write the answer from the preview rows using concrete numbers/names.
"""


BUSINESS_SCHEMA_GUIDE = """\
Business schema guide:

Core query model:
- `listings` is the central fact table. Each row is one listing.
- `listings.list_id` is the join key for all detail and attribute tables.
- Use `listings` for shared metadata only: title, description, price, price_text, category_id, root_category_id, category_group, category_name, region_id, region_name, area_name, ward_name, seller_name, status, list_time and date_text.
- Use detail tables for domain-specific attributes. Do not replace a detail-table concept with `listings.category_name`.
- Do not use SQLite views. Use base tables and explicit joins.
- Prefer readable aliases: `l`, `r`, `v`, `e`, `p`, `j`, `s`, `pet`, `c`, `la`.

Join map:
- `real_estate_details r` joins with `r.list_id = l.list_id`.
- `vehicle_details v` joins with `v.list_id = l.list_id`.
- `electronics_details e` joins with `e.list_id = l.list_id`.
- `product_details p` joins with `p.list_id = l.list_id`.
- `job_details j` joins with `j.list_id = l.list_id`.
- `service_details s` joins with `s.list_id = l.list_id`.
- `pet_details pet` joins with `pet.list_id = l.list_id`.
- `listing_attributes la` joins with `la.list_id = l.list_id`.
- Root category: join `categories c` with `c.category_id = l.root_category_id`.
- Current category: join `categories c` with `c.category_id = l.category_id`.

Counting rules:
- If `listing_attributes` is joined, listing rows may multiply.
- Use `COUNT(DISTINCT l.list_id)` for listing counts when joining one-to-many tables.
- Use `COUNT(la.attribute_id)` for number of extra attributes.
- For averages over listings while joining one-to-many tables, pre-aggregate the one-to-many table in a CTE first.

Domain concept map:
- Real estate: `category_group = 'real_estate'`; type -> `r.property_type`; sale/rent listing intent -> `r.listing_type`; area/m2 -> `r.area_m2`; rooms/bedrooms -> `r.rooms`; toilets/WC -> `r.toilets`; floors -> `r.floors`; legal paper -> `r.legal_document`; furnishing -> `r.furnishing`; street -> `r.street_name`; price per m2 -> `r.price_per_m2`.
- Vehicles: vehicle type -> `v.vehicle_type`; brand/make -> `v.brand`; model/line -> `v.model`; year -> `v.year`; mileage/km -> `v.mileage_km`; fuel -> `v.fuel`; condition -> `v.condition`.
- Electronics: electronics type -> `e.electronics_type`; brand -> `e.brand`; model -> `e.model`; condition -> `e.condition`; warranty -> `e.warranty`; capacity/storage -> `e.capacity`.
- General products: product type -> `p.product_type`; item type -> `p.item_type`; condition -> `p.condition`.
- Jobs: job type -> `j.job_type`; title -> `j.job_title`; company -> `j.company_name`; salary -> `j.salary_min`, `j.salary_max` or `j.salary_text`; contract -> `j.contract_type`; gender -> `j.preferred_gender`; experience -> `j.experience`; work location -> `j.work_location`; urgent -> `j.urgent`.
- Services: service type -> `s.service_type`; price unit -> `s.price_unit`; minimum price -> `s.min_price`.
- Pets: pet type -> `pet.pet_type`; breed -> `pet.breed`; age -> `pet.age`.
- Categories: root category -> `c.category_name` through `l.root_category_id`; current category -> `l.category_name` or `c.category_name` through `l.category_id`.
- Extra attributes: additional/custom/raw attributes -> `listing_attributes`.

Common value mapping:
- "TP.HCM", "HCM", "Ho Chi Minh", "Sai Gon" -> `l.region_name = 'Tp Hồ Chí Minh'`.
- "Ha Noi", "Hanoi" -> `l.region_name = 'Hà Nội'`.
- "iPhone" -> `e.electronics_type = 'Điện thoại'`, `e.brand = 'Apple'`, and model/title matching iPhone when needed.
"""


@dataclass
class SQLAttempt:
    sql: str
    ok: bool
    error: str | None = None
    preview_csv: str = ""
    preview_row_count: int = 0
    truncated: bool = False


@dataclass
class Text2SQLResult:
    question: str
    db_path: str
    model: str
    answer: str
    sql: str
    terminated: bool
    rounds: int
    attempts: list[SQLAttempt] = field(default_factory=list)
    conversation: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, include_conversation: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        payload["attempts"] = [asdict(attempt) for attempt in self.attempts]
        if not include_conversation:
            payload.pop("conversation", None)
        return payload


def parse_tool_call(content: str) -> tuple[str, dict[str, str]] | None:
    match = TOOL_CALL_RE.search(content or "")
    if not match:
        return None
    block = match.group(1)
    function_match = FUNC_RE.search(block)
    if not function_match:
        return None
    params = {name: value.strip() for name, value in PARAM_RE.findall(block)}
    return function_match.group(1).strip(), params


def sql_attempt_from_result(result: dict[str, Any], fallback_sql: str = "") -> SQLAttempt:
    return SQLAttempt(
        sql=result.get("sql", fallback_sql),
        ok=bool(result.get("ok")),
        error=result.get("error"),
        preview_csv=result.get("csv", ""),
        preview_row_count=int(result.get("preview_row_count", 0) or 0),
        truncated=bool(result.get("truncated", False)),
    )


def normalize_question_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_accents.replace("\u0111", "d")


def has_any(text: str, *keywords: str) -> bool:
    return any(keyword in text for keyword in keywords)


def infer_semantic_hints(question: str) -> list[str]:
    q = normalize_question_text(question)
    hints = [
        "First map every user concept to the most specific normalized table/column.",
        "Use `listings` for shared metadata; use detail tables for domain-specific concepts.",
        "If the query joins a one-to-many table such as `listing_attributes`, protect listing counts with `COUNT(DISTINCT l.list_id)`.",
        "Use readable aliases (`l`, `r`, `v`, `e`, `p`, `j`, `s`, `pet`, `c`, `la`).",
    ]
    if has_any(q, "tp.hcm", "tphcm", "hcm", "ho chi minh", "sai gon", "saigon"):
        hints.append("Location maps to `l.region_name = 'Tp Hồ Chí Minh'`.")
    if has_any(q, "ha noi", "hanoi"):
        hints.append("Location maps to `l.region_name = 'Hà Nội'`.")
    if has_any(q, "danh muc goc", "root category"):
        hints.append("Root category requires `categories c` joined on `c.category_id = l.root_category_id`.")
    if has_any(q, "thuoc tinh bo sung", "extra attribute", "additional attribute"):
        hints.append("Extra attributes require `listing_attributes la`; use `COUNT(DISTINCT l.list_id)` for listing counts.")
    if has_any(q, "bat dong san", "nha dat", "real estate", "property"):
        hints.append("Real-estate questions usually filter `l.category_group = 'real_estate'` and join `real_estate_details r` for property attributes.")
    if has_any(q, "xe", "oto", "o to", "xe may", "vehicle", "car", "motorbike"):
        hints.append("Vehicle questions join `vehicle_details v` for vehicle type, brand, model, year, mileage, fuel or condition.")
    if has_any(q, "dien thoai", "iphone", "ipad", "laptop", "may tinh", "do dien tu", "electronics"):
        hints.append("Electronics questions join `electronics_details e` for electronics type, brand, model, warranty, capacity or condition.")
    if has_any(q, "viec lam", "cong viec", "luong", "salary", "hop dong", "kinh nghiem", "job"):
        hints.append("Job questions join `job_details j` for salary, contract, title, company, gender, experience, work location or urgent flag.")
    if has_any(q, "dich vu", "service", "don vi gia", "price unit", "min price"):
        hints.append("Service questions join `service_details s` for service type, price unit or minimum price.")
    if has_any(q, "thu cung", "pet", "cho ", "meo", "giong", "breed"):
        hints.append("Pet questions join `pet_details pet` for pet type, breed or age.")
    return hints


def infer_sql_requirements(question: str) -> list[tuple[str, tuple[str, ...]]]:
    q = normalize_question_text(question)
    requirements: list[tuple[str, tuple[str, ...]]] = []

    add_requirement(requirements, q, ("danh muc goc", "root category"), "root category questions must join categories", ("categories",))
    if has_any(q, "thuoc tinh bo sung", "extra attribute", "additional attribute"):
        requirements.append(("extra attribute questions must use listing_attributes", ("listing_attributes",)))
        if has_any(q, "bao nhieu tin", "so luong tin", "count listings", "listing count"):
            requirements.append(("listing counts with listing_attributes must use COUNT(DISTINCT ...list_id)", ("count(distinct", "list_id")))

    add_domain_requirements(requirements, q)
    return requirements


def add_requirement(
    requirements: list[tuple[str, tuple[str, ...]]],
    q: str,
    keywords: tuple[str, ...],
    description: str,
    terms: tuple[str, ...],
) -> None:
    if has_any(q, *keywords):
        requirements.append((description, terms))


def add_domain_requirements(requirements: list[tuple[str, tuple[str, ...]]], q: str) -> None:
    if has_any(q, "bat dong san", "nha dat", "real estate", "property"):
        for keywords, description, terms in [
            (("loai bat dong san", "loai bds", "property type"), "real-estate type must use real_estate_details.property_type", ("real_estate_details", "property_type")),
            (("loai tin", "dang ban", "cho thue", "can ban", "can thue"), "real-estate sale/rent intent must use real_estate_details.listing_type", ("real_estate_details", "listing_type")),
            (("dien tich", "m2", "met vuong"), "area constraints must use real_estate_details.area_m2", ("real_estate_details", "area_m2")),
            (("phong ngu", "so phong", "rooms"), "room constraints must use real_estate_details.rooms", ("real_estate_details", "rooms")),
            (("toilet", "nha ve sinh", "wc"), "toilet constraints must use real_estate_details.toilets", ("real_estate_details", "toilets")),
            (("tang", "so tang"), "floor constraints must use real_estate_details.floors", ("real_estate_details", "floors")),
            (("phap ly", "so hong", "so do"), "legal-document constraints must use real_estate_details.legal_document", ("real_estate_details", "legal_document")),
            (("noi that",), "furnishing constraints must use real_estate_details.furnishing", ("real_estate_details", "furnishing")),
            (("gia/m2", "gia moi m2", "gia m2"), "price-per-square-meter questions must use real_estate_details.price_per_m2", ("real_estate_details", "price_per_m2")),
        ]:
            add_requirement(requirements, q, keywords, description, terms)

    for keywords, description, terms in [
        (("hang xe", "vehicle brand"), "vehicle brand questions must use vehicle_details.brand", ("vehicle_details", "brand")),
        (("dong xe", "mau xe", "model xe"), "vehicle model questions must use vehicle_details.model", ("vehicle_details", "model")),
        (("loai xe",), "vehicle type questions must use vehicle_details.vehicle_type", ("vehicle_details", "vehicle_type")),
        (("nam san xuat", "doi xe"), "vehicle year questions must use vehicle_details.year", ("vehicle_details", "year")),
        (("so km", "mileage", "km da di"), "vehicle mileage questions must use vehicle_details.mileage_km", ("vehicle_details", "mileage_km")),
        (("nhien lieu", "fuel"), "vehicle fuel questions must use vehicle_details.fuel", ("vehicle_details", "fuel")),
        (("iphone",), "iPhone questions must use electronics_details and explicitly match iPhone in model/title", ("electronics_details", "iphone")),
        (("hang dien thoai", "hang laptop"), "electronics brand questions must use electronics_details.brand", ("electronics_details", "brand")),
        (("model dien thoai", "model laptop"), "electronics model questions must use electronics_details.model", ("electronics_details", "model")),
        (("bao hanh", "warranty"), "warranty questions must use electronics_details.warranty", ("electronics_details", "warranty")),
        (("dung luong", "capacity", "storage"), "capacity questions must use electronics_details.capacity", ("electronics_details", "capacity")),
        (("loai san pham",), "product type questions must use product_details.product_type", ("product_details", "product_type")),
        (("kieu hang", "item type"), "item type questions must use product_details.item_type", ("product_details", "item_type")),
        (("luong", "salary"), "salary questions must use job_details salary fields", ("job_details", "salary")),
        (("hop dong", "contract"), "contract questions must use job_details.contract_type", ("job_details", "contract_type")),
        (("loai dich vu",), "service type questions must use service_details.service_type", ("service_details", "service_type")),
        (("gia toi thieu", "min price"), "minimum-price questions must use service_details.min_price", ("service_details", "min_price")),
        (("giong", "breed"), "pet breed questions must use pet_details.breed", ("pet_details", "breed")),
    ]:
        add_requirement(requirements, q, keywords, description, terms)


def validate_sql_semantics(sql: str, requirements: list[tuple[str, tuple[str, ...]]]) -> str | None:
    normalized_sql = re.sub(r"\s+", " ", sql.casefold())
    errors: list[str] = []
    for description, required_terms in requirements:
        missing = [term for term in required_terms if term.casefold() not in normalized_sql]
        if missing:
            errors.append(f"{description}; missing SQL term(s): {', '.join(missing)}")
    return " | ".join(errors) if errors else None


class Text2SQLAgent:
    """Iterative Vertex AI -> SQL tool -> Vertex AI loop."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        model: str = DEFAULT_MODEL,
        vertex_project: str | None = DEFAULT_VERTEX_PROJECT,
        vertex_location: str | None = DEFAULT_VERTEX_LOCATION,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        schema_sample_rows: int = DEFAULT_SCHEMA_SAMPLE_ROWS,
        result_limit: int = DEFAULT_RESULT_LIMIT,
    ):
        self.db_path = Path(db_path).resolve()
        self.model = model
        self.vertex_project = vertex_project
        self.vertex_location = vertex_location
        self.max_rounds = max_rounds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.schema_sample_rows = schema_sample_rows
        self.result_limit = result_limit

    def _build_user_prompt(self, question: str, external_context: str | None = None) -> str:
        schema_markdown = SchemaInspector(self.db_path).to_markdown(
            sample_rows=self.schema_sample_rows
        )
        context = external_context.strip() if external_context else "None"
        semantic_hints = "\n".join(f"- {hint}" for hint in infer_semantic_hints(question))
        return (
            f"Question:\n{question}\n\n"
            f"External context:\n{context}\n\n"
            f"{BUSINESS_SCHEMA_GUIDE}\n\n"
            f"Question-specific semantic hints:\n{semantic_hints}\n\n"
            f"Schema:\n{schema_markdown}\n\n"
            "Start by writing the best SQLite query for this question. "
            "Run it with execute_sql, inspect the result, then terminate with final SQL and answer."
        )

    def run(
        self,
        question: str,
        external_context: str | None = None,
        include_conversation: bool = False,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> Text2SQLResult:
        if not question.strip():
            raise ValueError("Question is required.")
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.db_path}")

        llm = VertexAIClient(project=self.vertex_project, location=self.vertex_location)
        semantic_requirements = infer_sql_requirements(question)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._build_user_prompt(question, external_context)},
        ]
        conversation: list[dict[str, Any]] = list(messages)
        attempts: list[SQLAttempt] = []
        final_sql = ""
        final_answer = ""
        terminated = False
        round_number = 0

        emit(on_event, "start", question=question, db_path=str(self.db_path), model=self.model)

        for round_number in range(1, self.max_rounds + 1):
            emit(on_event, "round_start", round=round_number)
            response_text = self._generate_with_retries(llm, messages)
            emit(on_event, "llm_response", round=round_number, content=response_text)
            messages.append({"role": "assistant", "content": response_text})
            conversation.append({"role": "assistant", "content": response_text})

            parsed = parse_tool_call(response_text)
            if not parsed:
                reminder = "Please call exactly one tool using the required <tool_call> format. Use execute_sql or terminate."
                messages.append({"role": "user", "content": reminder})
                conversation.append({"role": "user", "content": reminder})
                continue

            function_name, params = parsed
            emit(on_event, "tool_call", round=round_number, function=function_name, params=params)

            if function_name == "execute_sql":
                handle_execute_sql(self, params, messages, conversation, attempts, round_number, on_event)
                continue

            if function_name == "terminate":
                outcome = handle_terminate(
                    self,
                    params,
                    messages,
                    conversation,
                    attempts,
                    semantic_requirements,
                    round_number,
                    on_event,
                )
                if outcome is None:
                    continue
                final_sql, final_answer = outcome
                terminated = True
                break

            warning = f"Unknown tool: {function_name}. Use execute_sql or terminate."
            messages.append({"role": "user", "content": warning})
            conversation.append({"role": "user", "content": warning})

        if not terminated:
            final_sql, final_answer = fallback_answer(attempts)
            emit(on_event, "incomplete", rounds=round_number)

        if not include_conversation:
            conversation = []

        return Text2SQLResult(
            question=question,
            db_path=str(self.db_path),
            model=self.model,
            answer=final_answer,
            sql=final_sql,
            terminated=terminated,
            rounds=round_number,
            attempts=attempts,
            conversation=conversation,
        )

    def _generate_with_retries(self, llm: VertexAIClient, messages: list[dict[str, str]]) -> str:
        response_text = ""
        last_error: Exception | None = None
        for attempt_number in range(1, 4):
            try:
                response_text = llm.generate(
                    messages=messages,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                break
            except Exception as exc:
                last_error = exc
                time.sleep(min(2, attempt_number))
        if not response_text:
            raise RuntimeError(f"Vertex AI returned no content. Last error: {last_error}")
        return response_text


def handle_execute_sql(
    agent: Text2SQLAgent,
    params: dict[str, str],
    messages: list[dict[str, str]],
    conversation: list[dict[str, Any]],
    attempts: list[SQLAttempt],
    round_number: int,
    on_event: Callable[[dict[str, Any]], None] | None,
) -> None:
    sql = params.get("sql", "")
    result = execute_sqlite_sql(sql, agent.db_path, row_limit=agent.result_limit)
    attempts.append(sql_attempt_from_result(result, fallback_sql=sql))
    tool_payload = tool_payload_from_result("execute_sql", result)
    tool_message = "EXECUTION RESULT of [execute_sql]:\n" + json.dumps(
        tool_payload, ensure_ascii=False, indent=2
    )
    if result.get("ok"):
        tool_message += (
            "\n\nIf this result answers the user's question, your next response "
            "must call terminate with the exact SQL that just succeeded and a concise answer. "
            "Use the preview rows to include concrete values; do not answer only that the result was calculated."
        )
    messages.append({"role": "user", "content": tool_message})
    conversation.append({"role": "tool", "content": tool_payload})
    emit(on_event, "tool_result", round=round_number, result=tool_payload)


def handle_terminate(
    agent: Text2SQLAgent,
    params: dict[str, str],
    messages: list[dict[str, str]],
    conversation: list[dict[str, Any]],
    attempts: list[SQLAttempt],
    semantic_requirements: list[tuple[str, tuple[str, ...]]],
    round_number: int,
    on_event: Callable[[dict[str, Any]], None] | None,
) -> tuple[str, str] | None:
    final_sql = params.get("sql", "").strip()
    final_answer = params.get("answer", "").strip()
    if not attempts:
        return reject_terminate(messages, conversation, "Run at least one query with execute_sql before terminate.")
    if not final_sql or not final_answer:
        return reject_terminate(messages, conversation, "terminate requires both sql and answer parameters.")

    validation = execute_sqlite_sql(final_sql, agent.db_path, row_limit=agent.result_limit)
    attempts.append(sql_attempt_from_result(validation, fallback_sql=final_sql))
    validation_payload = tool_payload_from_result("validate_final_sql", validation)
    conversation.append({"role": "tool", "content": validation_payload})
    emit(on_event, "tool_result", round=round_number, result=validation_payload)

    if not validation.get("ok"):
        reminder = "The SQL submitted to terminate did not execute successfully. Fix it, run execute_sql again, then terminate."
        messages.append(
            {
                "role": "user",
                "content": "EXECUTION RESULT of [validate_final_sql]:\n"
                + json.dumps(validation_payload, ensure_ascii=False, indent=2)
                + "\n\n"
                + reminder,
            }
        )
        conversation.append({"role": "user", "content": reminder})
        return None

    semantic_error = validate_sql_semantics(final_sql, semantic_requirements)
    if semantic_error:
        reminder = (
            "The SQL submitted to terminate executed successfully but does not match "
            f"the question semantics: {semantic_error}. Rewrite the SQL using the most "
            "specific normalized table/column, run execute_sql again, then terminate."
        )
        messages.append({"role": "user", "content": reminder})
        conversation.append({"role": "user", "content": reminder})
        emit(on_event, "semantic_validation_error", round=round_number, error=semantic_error, sql=final_sql)
        return None

    emit(on_event, "terminated", sql=final_sql, answer=final_answer)
    return final_sql, final_answer


def reject_terminate(
    messages: list[dict[str, str]],
    conversation: list[dict[str, Any]],
    reminder: str,
) -> None:
    messages.append({"role": "user", "content": reminder})
    conversation.append({"role": "user", "content": reminder})
    return None


def tool_payload_from_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "ok": result.get("ok"),
        "sql": result.get("sql"),
        "error": result.get("error"),
        "content": result.get("content"),
        "elapsed_seconds": result.get("elapsed_seconds"),
    }


def fallback_answer(attempts: list[SQLAttempt]) -> tuple[str, str]:
    last_ok = next((attempt for attempt in reversed(attempts) if attempt.ok), None)
    if not last_ok:
        return "", "Agent did not terminate within the round limit."
    answer = (
        "Agent did not call terminate within the round limit, but the last SQL query "
        "executed successfully."
    )
    if last_ok.preview_csv.strip():
        answer += f"\n\nLast result preview:\n{last_ok.preview_csv.strip()}"
    return last_ok.sql, answer


def emit(
    on_event: Callable[[dict[str, Any]], None] | None,
    event_type: str,
    **payload: Any,
) -> None:
    if on_event:
        on_event({"type": event_type, **payload})


def run_text2sql(
    question: str,
    db_path: str | Path = DEFAULT_DB_PATH,
    model: str = DEFAULT_MODEL,
    vertex_project: str | None = DEFAULT_VERTEX_PROJECT,
    vertex_location: str | None = DEFAULT_VERTEX_LOCATION,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    temperature: float = DEFAULT_TEMPERATURE,
    external_context: str | None = None,
    include_conversation: bool = False,
) -> Text2SQLResult:
    agent = Text2SQLAgent(
        db_path=db_path,
        model=model,
        vertex_project=vertex_project,
        vertex_location=vertex_location,
        max_rounds=max_rounds,
        temperature=temperature,
    )
    return agent.run(
        question=question,
        external_context=external_context,
        include_conversation=include_conversation,
    )
