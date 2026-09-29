"""Shared test data."""
from __future__ import annotations

import json

FINVIZ_HTML = """
<html><body>
<table class="styled-table-new">
  <tr class="news_table-row">
    <td class="news_date-cell">5 min</td>
    <td>
      <div class="news-badges-container">
        <a class="nn-tab-link" rel="nofollow"
           href="https://www.Example.com/Markets/Nvidia-Beats?utm_source=finviz#top">Nvidia beats estimates as data-center sales double</a>
        <span class="news_date-cell">Reuters</span>
      </div>
      <a class="fv-label stock-news-label" data-boxover-company="NVIDIA Corp"
         data-boxover-industry="Semiconductors" data-boxover-country="USA">
        <span class="select-none font-semibold">NVDA</span>+2.50%</a>
      <a class="fv-label stock-news-label"><span class="select-none font-semibold">NVDA</span>+0.40% AH</a>
      <span class="fv-label">+3 More</span>
    </td>
  </tr>
  <tr class="news_table-row">
    <td class="news_date-cell">2 hours</td>
    <td>
      <div class="news-badges-container">
        <a class="nn-tab-link" href="/news/123/Acme-Declares-Quarterly-Dividend">Acme Declares Quarterly Dividend of $0.25</a>
        <span class="news_date-cell">GlobeNewswire</span>
      </div>
      <a class="fv-label stock-news-label" data-boxover-industry="Banks - Regional">
        <span class="select-none font-semibold">ACME</span>-0.10%</a>
    </td>
  </tr>
  <tr class="news_table-row">
    <td class="news_date-cell">Sep-19</td>
    <td><div class="news-badges-container">
      <a class="nn-tab-link" rel="nofollow" href="https://macro.example.org/fed-holds-rates">Fed holds rates steady</a>
      <span class="news_date-cell">Bloomberg</span></div></td>
  </tr>
  <tr class="news_table-row"><td class="news_date-cell">1 min</td><td>malformed row</td></tr>
</table>
</body></html>
"""

ARTICLE_BODY = (
    "NVIDIA reported quarterly revenue of $30.0 billion, up 122% from a year ago. "
    "“Demand for Blackwell is incredible,” said CEO Jensen Huang. "
    "Data-center revenue was $26.3 billion."
)

ARTICLE_PAGE_HTML = f"<html><body><article><h1>Nvidia</h1><p>{ARTICLE_BODY}</p><p>{ARTICLE_BODY}</p></article></body></html>"

GOOD_EXTRACTION = {
    "tickers": ["NVDA"],
    "event_type": "earnings",
    "sentiment": "bullish",
    "key_facts": ["Revenue $30.0 billion, up 122%"],
    "numbers": [{"value": "30.0", "unit": "billion USD", "context": "revenue"}],
    "one_line": "Nvidia revenue jumped 122% on data-center demand.",
    "evidence": '"Demand for Blackwell is incredible," said CEO Jensen Huang.',
}
GOOD_EXTRACTION_JSON = json.dumps(GOOD_EXTRACTION)

REPORT_MARKDOWN = (
    "## Market Overview\n\nChip stocks led after Nvidia's results [1].\n\n"
    "## Technology\n\n- Nvidia revenue jumped 122% [1].\n\n## What to Watch\n\n- Guidance updates.\n" * 3
)
