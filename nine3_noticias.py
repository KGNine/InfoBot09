# nine3_noticias.py - Nine3, jornalista economico da L.I.C.A.
# Escolhe as noticias de MAIOR IMPACTO no momento do lancamento.
# Usa so requests + biblioteca padrao. Uso: from nine3_noticias import escolher
import re, html, unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import requests

# Troque/acrescente pelos feeds RSS que voce ja usa no conteudo_gratuito.py.
# Feed fora do ar e ignorado (aparece "falhou" no log).
FEEDS = {
    "G1 Economia": "https://g1.globo.com/rss/g1/economia/",
    "InfoMoney": "https://www.infomoney.com.br/feed/",
    "Money Times": "https://www.moneytimes.com.br/feed/",
    "Agencia Brasil": "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml",
    "Cointelegraph BR": "https://br.cointelegraph.com/rss",
}

# Peso de impacto por palavra (sem acento, minusculo)
T1 = ["copom", "selic", "juros", "inflacao", "ipca", "pib", "fed", "payroll", "banco central",
      "tarifa", "recessao", "fiscal", "arcabouco", "default", "guerra", "sancoes"]
T2 = ["dolar", "ibovespa", "bitcoin", "petroleo", "ouro", "etf", "recorde", "bce", "china",
      "eua", "emprego", "desemprego", "bolsa", "cambio", "ethereum", "nvidia", "openai"]
T3 = ["alta", "queda", "dispara", "despenca", "balanco", "lucro", "dividendos", "acoes"]
PESOS = {**{p: 5 for p in T1}, **{p: 3 for p in T2}, **{p: 1 for p in T3}}

# Descartar: nao gera valor para o grupo
LIXO = ["horoscopo", "loteria", "mega-sena", "bolao", "concurso", "patrocinado", "podcast",
        "receita de", "futebol", "novela", "bbb", "cupom", "oferta", "promocao"]

# Afinidade por pilar de noticia
PILARES = {
    "Cripto Pulse": ["bitcoin", "cripto", "ethereum", "etf", "blockchain", "stablecoin", "solana"],
    "Termometro BR": ["brasil", "selic", "copom", "ipca", "ibovespa", "real", "governo", "fiscal", "pib"],
    "Giro Global": ["fed", "eua", "china", "europa", "bce", "petroleo", "tarifa", "payroll", "japao", "guerra"],
    "Radar IA": ["ia", "inteligencia artificial", "openai", "nvidia", "anthropic", "chip", "google"],
}
STOP = set("para com uma que dos das por mais como sobre apos entre sera foi nao seu sua mas ainda".split())


def norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 \-]", " ", t)).strip()


def tokens(t):
    return {w for w in norm(t).split() if len(w) > 3 and w not in STOP}


def limpa(t, n=300):
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "..."


def _data(s):
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        except Exception:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def parse_feed(xml_bytes, fonte):
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        def g(*nomes):
            for n in nomes:
                for c in it:
                    if c.tag.split("}")[-1] == n:
                        return c
            return None
        t, l = g("title"), g("link")
        d = g("description", "summary", "content")
        p = g("pubDate", "published", "updated")
        link = (l.get("href") if l is not None and l.get("href") else (l.text if l is not None else "")) or ""
        if t is None or not (t.text or "").strip():
            continue
        out.append({"titulo": limpa(t.text, 200), "resumo": limpa(d.text if d is not None else ""),
                    "link": link.strip(), "fonte": fonte, "publicado": _data(p.text if p is not None else None)})
    return out


def coletar(feeds=None, log=print):
    itens = []
    for nome, url in (feeds or FEEDS).items():
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (L.I.C.A. Nine3)"})
            r.raise_for_status()
            lote = parse_feed(r.content, nome)
            log(f"[Nine3] {nome}: {len(lote)} noticias")
            itens += lote
        except Exception as e:
            log(f"[Nine3] {nome}: falhou ({e})")
    return itens


def _palavras_peso(texto):
    n = " " + norm(texto) + " "
    return sum(p for k, p in PESOS.items() if f" {k} " in n or f" {k}s " in n)


def pontuar(itens, horas=12, agora=None):
    agora = agora or datetime.now(timezone.utc)
    vivos = []
    for i in itens:
        base = i["titulo"] + " " + i["resumo"]
        if any(x in norm(base) for x in LIXO):
            continue
        idade = (agora - i["publicado"]).total_seconds() / 3600 if i["publicado"] else None
        if idade is not None and (idade > horas or idade < -1):
            continue
        i["idade_h"] = idade
        vivos.append(i)
    grupos = []  # agrupa a mesma noticia vinda de varias fontes
    for i in sorted(vivos, key=lambda x: -len(x["resumo"])):
        tk = tokens(i["titulo"])
        for g in grupos:
            u = tk | g["tk"]
            if u and len(tk & g["tk"]) / len(u) >= 0.35:
                g["itens"].append(i)
                break
        else:
            grupos.append({"tk": tk, "itens": [i]})
    res = []
    for g in grupos:
        rep = g["itens"][0]
        fontes = sorted({x["fonte"] for x in g["itens"]})
        impacto = min(_palavras_peso(rep["titulo"] + " " + rep["resumo"]), 15)
        rec = 0 if rep["idade_h"] is None else 6 * max(0, 1 - rep["idade_h"] / horas)
        score = 3 * (len(fontes) - 1) + impacto + rec
        res.append({**rep, "fontes": fontes, "score": round(score, 1)})
    return sorted(res, key=lambda x: -x["score"])


def escolher(pilar=None, n=1, horas=12, ja_postados=(), feeds=None, itens=None, log=print):
    """Devolve as n melhores noticias para o pilar (ou gerais).
    ja_postados: links/titulos ja enviados, para nao repetir."""
    itens = itens if itens is not None else coletar(feeds, log)
    ranking = pontuar(itens, horas)
    usados = {norm(x) for x in ja_postados}
    out = []
    for r in ranking:
        if r["link"] and norm(r["link"]) in usados or norm(r["titulo"]) in usados:
            continue
        if pilar in PILARES:
            n_txt = " " + norm(r["titulo"] + " " + r["resumo"]) + " "
            if not any(f" {k} " in n_txt for k in PILARES[pilar]):
                continue
        out.append(r)
        if len(out) == n:
            break
    return out


def post_gratis(r, limite=280):
    """Conteudo padrao do grupo gratis: manchete + resumo curto + fonte(s)."""
    resumo = limpa(r["resumo"], limite)
    return {"manchete": r["titulo"], "resumo": resumo, "fontes": ", ".join(r["fontes"]), "link": r["link"]}


def pedido_vip(r):
    """Prompt para a API escrever o texto completo do VIP (com palavras proprias)."""
    return (
        "Voce e o Nine3, jornalista economico da L.I.C.A. Escreva para o grupo VIP, em portugues, "
        "com palavras proprias (nao copie frases da fonte): 1) o fato em 3 linhas; 2) por que importa "
        "para o mercado; 3) o que observar a seguir; 4) uma pergunta para o grupo responder. "
        "Sem prometer ganhos. Termine com: 'Conteudo informativo, nao e recomendacao de investimento.'\n\n"
        f"Manchete: {r['titulo']}\nResumo: {r['resumo']}\nFontes: {', '.join(r['fontes'])}"
    )


if __name__ == "__main__":
    for p in [None, "Termometro BR", "Giro Global", "Cripto Pulse", "Radar IA"]:
        top = escolher(p, n=2)
        print(f"\n== {p or 'Geral'}")
        for t in top:
            print(f"{t['score']:>5} | {t['titulo']} | {', '.join(t['fontes'])}")
