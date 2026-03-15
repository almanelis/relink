# coverage report

отчет сформирован командой:

```bash
coverage run -m pytest tests
coverage report -m
coverage html
```

## итог

- всего тестов: `22`
- успешно: `22`
- общее покрытие: `97%`

файл html-отчета генерируется в `htmlcov/index.html` локально.
подробный текстовый срез также сохранен в `coverage_report.txt`.
