# AI Resume Analyzer

A Streamlit application that evaluates pasted resume text against an optional
job description and returns an ATS score, keyword analysis, truthful bullet
improvements, and actionable recommendations.

## Features

- Resume analysis using the OpenAI API
- ATS score with keyword, experience relevance, and formatting breakdown
- Matched keywords, missing keywords, and critical skill gaps
- Bullet rewrites that do not invent candidate experience or metrics
- General resume audit when no job description is supplied
- Downloadable JSON report
- Optional local report history stored in SQLite
- Input validation and deterministic tests with a mocked AI client

## Architecture

```text
Streamlit UI (app/main.py)
  -> ResumeAnalyzer (app/services/resume_service.py)
       -> Prompt (app/prompts/resume_prompt.py)
       -> OpenAI API
  -> ReportRepository (app/services/report_repository.py)
       -> Local SQLite database (opt-in report storage)
```

The original resume text is not stored by the application. Analysis requests are
sent to the configured AI provider. Saving a generated report is optional and
off by default; saved report text can still contain personal information.

## Installation

Python 3.10 or later is recommended.

Run the setup commands from the repository root (the `resume-analyser` folder
containing `requirements.txt`). If you have not cloned the repository yet:

```bash
git clone https://github.com/pavankumargp6/resume-analyser.git
cd resume-analyser
```

If you already cloned it, change into that folder first. For example, from
`C:\Users\pavan`, run `Set-Location .\resume-analyser` in PowerShell.

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

## Setup

Set `OPENAI_API_KEY` in `.env`. The `.env` file is ignored by Git. Do not commit
API keys or real resumes.

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key; required for analysis | — |
| `OPENAI_MODEL` | OpenAI chat model | `gpt-4o-mini` |
| `MAX_RESUME_CHARS` | Maximum accepted resume length | `30000` |
| `OPENAI_TIMEOUT_SECONDS` | Request timeout | `45` |
| `RESUME_ANALYZER_DB_PATH` | SQLite path for opted-in saved reports | `.data/analyses.sqlite3` |

## Run the application

```bash
python -m streamlit run app/main.py
```

Paste resume text and, optionally, a target job description before selecting
**Analyze resume**. Without a job description, the app performs a general
technical resume audit. To save a report locally, opt in using the checkbox
before submitting. Use the saved reports panel to review or delete saved
reports.

## Run tests

```bash
python -m pytest
```

Tests use a fake OpenAI client and make no network calls or require a real API
key.

## Troubleshooting

- **`OPENAI_API_KEY is not configured`**: add a valid key to `.env`.
- **AI provider request failed**: verify network access, account/API availability,
  model configuration, and try again.
- **Report could not be saved**: verify the configured database directory is
  writable.
- **Resume is too long**: shorten it or adjust `MAX_RESUME_CHARS`.

## Security and privacy

- Treat resume text as sensitive personal data. Submit only content you are
  authorized to process.
- Resume text is sent to the configured AI provider; review that provider's
  privacy and retention terms before use.
- Generated reports are saved locally only after explicit opt-in. The database
  may contain personal information from the report; protect and delete it when
  no longer needed.
- Keep `.env`, the SQLite database, and untrusted resume data out of source
  control. Do not log resume text or API keys.
- This workshop application is a prototype and should not be used for
  consequential hiring decisions without appropriate human review and a formal
  privacy, fairness, and security assessment.

## Future enhancements

- PDF/DOCX parsing with file-size and content validation
- Export to accessible PDF
- User accounts and managed retention controls
- Human-reviewed role taxonomy and configurable job listings
- Evaluation of output quality, bias, and model changes
