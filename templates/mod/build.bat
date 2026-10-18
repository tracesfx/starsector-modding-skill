@echo off
rem One-command build for {{MOD_NAME}}: compile src\ -> jars\{{JAR_NAME}}.jar -> validate.
cd /d "%~dp0"
python tools\build_mod.py %*
exit /b %errorlevel%
