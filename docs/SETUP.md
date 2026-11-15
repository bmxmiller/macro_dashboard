# MacroLens setup guide

This guide takes you from nothing to a live, self-updating dashboard on GitHub Pages. No prior GitHub Actions experience is needed.

> **It costs £0, and you never need a card.** Every service below has a free tier that asks for an email sign-up only: FRED, Google AI Studio (Gemini), Groq, GitHub (public repo, Actions and Pages). If any sign-up page asks for payment details, you are on the wrong page. Stop and re-check the link.

Time needed: about 20 minutes.

---

## 1. Get the three free API keys

Keep the keys somewhere private, such as a password manager. Never paste them into code, issues or commits.

### 1a. FRED (economic data). Required.
1. Go to <https://fredaccount.stlouisfed.org/login/secure/> and create a free account.
2. Open <https://fredaccount.stlouisfed.org/apikeys> and click **Request API Key**.
3. Enter a short description (for example "personal macro dashboard"), accept the terms and submit.
4. Copy the 32-character key. This is your `FRED_API_KEY`.

### 1b. Google Gemini (AI summaries). Optional but recommended.
1. Go to <https://aistudio.google.com> and sign in with a Google account.
2. Click **Get API key** → **Create API key**.
3. Copy the key. This is your `GEMINI_API_KEY`. The free tier is enough, and you don't need to set up billing.

### 1c. Groq (AI fallback). Optional but recommended.
1. Go to <https://console.groq.com> and sign up (email, Google or GitHub).
2. Open **API Keys** → **Create API Key**, give it a name and copy it. This is your `GROQ_API_KEY`.

If you skip the AI keys, the data panels still work. Only the AI features are skipped.

---

## 2. Create the GitHub repository and push the code

1. Create a free account at <https://github.com> if you don't have one.
2. Click **+** → **New repository**.
   - Name: for example `macrolens`.
   - Visibility: **Public**. GitHub Pages and unlimited Actions minutes are free for public repos.
   - Don't add a README, .gitignore or licence, because the project already has them.
3. Push the project from your computer (replace `YOUR-USER`):
   ```bash
   cd path/to/Macro_Dashboard
   git init            # skip if it's already a git repo
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR-USER/macrolens.git
   git push -u origin main
   ```
   `.env` is in `.gitignore`, so your local keys are never uploaded. Check with `git status` that `.env` is not listed before you commit.

---

## 3. Add the secrets

GitHub Secrets are encrypted. Workflows can use them, but nobody, including you, can read them back after saving.

1. In your repo, open **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret** and add each of these (the names must match exactly):

   | Name             | Value                  |
   | ---------------- | ---------------------- |
   | `FRED_API_KEY`   | your FRED key          |
   | `GEMINI_API_KEY` | your Gemini key        |
   | `GROQ_API_KEY`   | your Groq key          |
   | `DATA_DEPLOY_KEY` | private SSH key the data bot pushes with (see 3b), only needed if you protect `main` |

### 3b. (Optional) Protect `main` and let the data bot push

The project's `main` branch is protected by a ruleset: changes need a pull request and three green checks (pytest, typecheck + build, Playwright), and force-push and deletion are blocked. The daily data job still has to commit to `main`, and a personal repo can't exempt the Actions bot, so the job pushes with a **deploy key**:

1. Generate a key pair: `ssh-keygen -t ed25519 -f data_deploy_key -N ""`.
2. **Settings** → **Deploy keys** → **Add deploy key**: paste `data_deploy_key.pub` and tick **Allow write access**.
3. Add the private half (`data_deploy_key`) as the `DATA_DEPLOY_KEY` secret, then delete both local files.
4. **Settings** → **Rules** → **Rulesets**: require a pull request and the three status checks on `main`, block force pushes and deletion, and add **Deploy keys** to the bypass list. That is the only bypass.

A useful side effect: pushes made with a deploy key (unlike the default `GITHUB_TOKEN`) trigger workflows, so every data commit runs the full CI suite before it is published. If you skip this step, leave `main` unprotected: with the secret unset, `actions/checkout` falls back to the default token, which can push to an unprotected branch (but its pushes do not trigger CI).

---

## 4. Turn on GitHub Pages

1. Open **Settings** → **Pages**.
2. Under **Build and deployment** → **Source**, choose **GitHub Actions**. Don't choose "Deploy from a branch".

That's the only Pages setting. The `deploy` workflow does the rest.

---

## 5. Trigger the first data run

1. Open the **Actions** tab. If GitHub asks you to enable workflows, click the button to enable them.
2. In the left sidebar, click **update-data** → **Run workflow** → **Run workflow**. Leave "sections" empty to build everything.
3. Wait a few minutes. When it finishes, the data commit triggers **ci**, and once that passes the **deploy** workflow publishes the site.
4. The site URL appears in the deploy run summary and under **Settings** → **Pages**. It looks like `https://YOUR-USER.github.io/macrolens/`.

### What runs automatically from now on

| Workflow      | When                                                                  | What it does                                                                       |
| ------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `ci`          | every push and pull request                                           | runs the Python tests, type-checks and builds the web app, and runs the Playwright browser tests |
| `update-data` | weekdays 22:30 UTC (after the US close), Saturdays 12:00 UTC, or manually | fetches data and commits changed `web/public/data/*.json`                          |
| `deploy`      | after `ci` passes on a push to `main` (including data commits), or manually | builds exactly the commit that passed and publishes it to GitHub Pages       |

To rebuild only some sections, use **Run workflow** with "sections" set to a space-separated list, for example `markets economy`.

### Troubleshooting
- **update-data is red but the site still updated.** One section failed, for example a data source was down. The other sections were still committed, and the failed panel keeps its last good data with a "stale" badge. Open the run's **Build data** step to see the error. It usually fixes itself on the next run.
- **"Permission denied" when the workflow pushes.** Open **Settings** → **Actions** → **General** → **Workflow permissions** and make sure workflows are allowed to write. The workflow also asks for `contents: write` itself.
- **deploy fails with a Pages error.** Check that step 4 is set to **GitHub Actions**.
- **Scheduled runs stopped.** GitHub pauses schedules in repos with no activity for 60 days. Re-enable the workflow from the Actions tab.

---

## 6. Run it locally (optional)

You need [Python 3.13](https://www.python.org/downloads/) and [Node.js 22](https://nodejs.org/), both free.

```bash
# 1. Python environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
pip install -r pipeline/requirements.txt

# 2. Local secrets: copy the template and fill in your keys
cp .env.example .env        # Windows (cmd): copy .env.example .env
#    then edit .env:  FRED_API_KEY=...  GEMINI_API_KEY=...  GROQ_API_KEY=...

# 3. Build the data (writes web/public/data/*.json)
python -m pipeline.build
python -m pipeline.build --only markets   # just one section

# 4. Tests
python -m pytest

# 5. Web app
cd web
npm install
npm run dev                  # opens http://localhost:5173
```

`.env` stays on your machine. It is gitignored, and GitHub uses the Secrets from step 3 instead.
