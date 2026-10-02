"""Refresh aggregate profile graphics with the locally authenticated GitHub CLI.

Run: python scripts/update-profile-stats.py
No credentials or private repository identifiers are written to output files.
An optional --input file accepts an already retrieved GraphQL response.
"""

import argparse
import collections
import datetime as dt
import html
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("JavaScript", "Python", "TypeScript", "Java", "C#", "Dart")
P = {"bg": "#101b26", "ink": "#eef0e9", "muted": "#b2c1c8", "amber": "#edb46a", "green": "#8eb7a4", "line": "#344451"}


def text(x, y, value, size=16, color="ink", weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{P[color]}" font-weight="{weight}">{html.escape(str(value))}</text>'


def svg(title, description, content):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="270" viewBox="0 0 400 270" role="img" aria-labelledby="title desc">'
            f'<title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(description)}</desc>'
            f'<rect x=".5" y=".5" width="399" height="269" rx="12" fill="{P["bg"]}" stroke="{P["line"]}"/>'
            '<g font-family="Segoe UI, Arial, sans-serif">' + content + '</g></svg>\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.input:
        response = json.loads(args.input.read_text(encoding="utf-8-sig"))
    else:
        today = dt.datetime.now(dt.timezone.utc).date()
        try:
            since = today.replace(year=today.year - 1)
        except ValueError:
            since = today.replace(year=today.year - 1, day=28)
        query = '''query { user(login: "igorhrmoraes") { login repositories(ownerAffiliations: OWNER, first: 100) {
          totalCount nodes { name isPrivate isFork isArchived languages(first: 50) { edges { node { name } } } }
        } contributionsCollection(from: "%sT00:00:00Z", to: "%sT23:59:59Z") {
          startedAt endedAt contributionCalendar { totalContributions }
        } } }''' % (since, today)
        raw = subprocess.run(["gh", "api", "graphql", "-f", "query=" + query], check=True, capture_output=True, text=True, encoding="utf-8")
        response = json.loads(raw.stdout)
    if response.get("errors"):
        raise RuntimeError("GitHub returned an incomplete response; no output updated.")
    user = response["data"]["user"]
    repositories = user["repositories"]
    if repositories["totalCount"] != len(repositories["nodes"]):
        raise RuntimeError("Repository result is incomplete; add pagination before updating.")
    repos = [r for r in repositories["nodes"] if not r["isArchived"] and r["name"].lower() != user["login"].lower()]
    counts = collections.Counter(e["node"]["name"] for r in repos for e in r["languages"]["edges"])
    collection = user["contributionsCollection"]
    end = dt.date.fromisoformat(collection["endedAt"][:10])
    start = dt.date.fromisoformat(collection["startedAt"][:10])
    date = end.strftime("%d/%m/%Y")
    total = len(repos)
    private = sum(r["isPrivate"] for r in repos)
    public = total - private
    contributions = collection["contributionCalendar"]["totalContributions"]
    languages = {lang: counts[lang] for lang in LANGUAGES}
    summary = {"updated": end.isoformat(), "period_start": start.isoformat(), "period_end": end.isoformat(),
               "project_repositories": total, "private": private, "public": public,
               "forks_included": sum(r["isFork"] for r in repos), "contributions": contributions,
               "selected_languages_by_repository": languages}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    activity = text(24, 33, "Projetos e atividade", 20, weight=600)
    activity += text(24, 99, total, 48, "amber", 600)
    activity += text(100, 77, "repositórios de projetos", 16) + text(100, 100, "não arquivados", 15, "muted")
    activity += text(24, 139, f"{private} privados · {public} público", 16, "muted")
    activity += f'<path d="M24 159H376" stroke="{P["line"]}"/>'
    activity += text(24, 218, contributions, 43, "green", 600)
    activity += text(126, 195, "contribuições", 17) + text(126, 219, "nos últimos 12 meses", 15, "muted")
    activity += text(24, 251, "GitHub · retrato em " + date, 14, "muted")
    (ROOT / "assets/activity.svg").write_text(svg("Projetos e atividade", f"{total} repositórios, {private} privados e {public} público. {contributions} contribuições nos últimos 12 meses. Atualizado em {date}.", activity), encoding="utf-8")

    bars = text(24, 33, "Linguagens nos projetos", 20, weight=600)
    bars += text(24, 57, "Presença por repositório · seleção de 6", 14, "muted")
    scale = max(languages.values(), default=1) or 1
    for index, (lang, count) in enumerate(languages.items()):
        y = 89 + index * 27
        bars += text(24, y + 5, lang, 16)
        bars += f'<rect x="125" y="{y - 9}" width="{208 * count / scale:g}" height="14" rx="3" fill="{P["amber"]}"/>'
        bars += text(350, y + 5, count, 16, weight=600)
    bars += text(24, 251, "Fonte: linguagens detectadas pelo GitHub.", 14, "muted")
    (ROOT / "assets/languages.svg").write_text(svg("Linguagens nos projetos", "; ".join(f"{k}: {v} repositórios" for k, v in languages.items()), bars), encoding="utf-8")

    details = f'''<sub>Dados de {date}. Repositórios próprios não arquivados, incluindo forks e excluindo este perfil.</sub>

<details>
<summary>Resumo acessível e como os números são contados</summary>

- **{total} repositórios de projetos:** {private} privados e {public} público; {summary["forks_included"]} fork incluído.
- **{contributions} contribuições** registradas pelo GitHub de {start.strftime("%d/%m/%Y")} a {date}, incluindo o total agregado de atividade privada. Contribuições não são sinônimo de commits.
- **Presença das linguagens:** {"; ".join(f"{k}: {v}" for k, v in languages.items())} repositório(s).

O gráfico conta em quantos repositórios cada linguagem selecionada aparece. Um projeto pode usar várias linguagens. Ele não mede proficiência, autoria de cada linha ou proporção de código, e não é uma lista de todas as linguagens detectadas pelo GitHub.

Os números são um retrato da data indicada, sem atualização automática. Nenhum nome ou conteúdo de projeto privado é exposto. [Dados agregados](data/summary.json) · [Rotina de atualização](scripts/update-profile-stats.py).

</details>'''
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    updated, matches = re.subn(r"<!-- STATS:START -->.*?<!-- STATS:END -->", "<!-- STATS:START -->\n" + details + "\n<!-- STATS:END -->", original, flags=re.S)
    if matches != 1:
        raise RuntimeError("Expected one statistics block in README.")
    path.write_text(updated, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
