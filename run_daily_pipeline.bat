@echo off
setlocal

cd /d "%~dp0"

if not exist "logs" mkdir "logs"

echo ============================================================>> "logs\scheduler.log"
echo START %date% %time%>> "logs\scheduler.log"

python -m Crawler.main >> "logs\crawler_scheduler.log" 2>&1
set CRAWLER_EXIT=%ERRORLEVEL%
echo CRAWLER_EXIT=%CRAWLER_EXIT%>> "logs\scheduler.log"

if not "%CRAWLER_EXIT%"=="0" (
  echo STOP crawler failed %date% %time%>> "logs\scheduler.log"
  exit /b %CRAWLER_EXIT%
)

python -m preprocessor.main >> "logs\preprocess_scheduler.log" 2>&1
set PREPROCESS_EXIT=%ERRORLEVEL%
echo PREPROCESS_EXIT=%PREPROCESS_EXIT%>> "logs\scheduler.log"
echo END %date% %time%>> "logs\scheduler.log"

exit /b %PREPROCESS_EXIT%
