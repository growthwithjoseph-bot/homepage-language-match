"""Homepage structured extraction (headlines vs paragraphs)."""
from backend.pipeline.homepage import extract_homepage

SAMPLE = """
<html><head><title>  Acme  Notes </title></head>
<body>
  <nav><h2>Home</h2><a href="/">Nav link text that should be ignored</a></nav>
  <h1>The AI notepad for meetings</h1>
  <h2>Effortless notes, enhanced instantly.</h2>
  <h2>Effortless notes, enhanced instantly.</h2>  <!-- dup -->
  <h3>Ok</h3>                                       <!-- too short -->
  <h4>Footer heading</h4>                           <!-- h4 ignored -->
  <p>Short</p>                                       <!-- too short -->
  <p>Granola helps you before, during and after your meetings every day.</p>
  <p>   </p>                                         <!-- empty -->
  <script>var x = 'h1 not a heading';</script>
  <footer><p>Copyright 2026 Acme. All rights reserved forever and always.</p></footer>
</body></html>
"""


def test_extracts_headlines_and_paragraphs():
    hp = extract_homepage(SAMPLE, "https://acme.com")
    assert hp.title == "Acme Notes"                       # whitespace collapsed
    # h1 + h2 kept; h4, too-short h3, and nav heading dropped; dup collapsed
    assert hp.headlines == [
        "The AI notepad for meetings",
        "Effortless notes, enhanced instantly.",
    ]
    # one real paragraph; short/empty/footer paragraphs dropped
    assert hp.paragraphs == [
        "Granola helps you before, during and after your meetings every day.",
    ]


def test_empty_and_malformed_html_is_safe():
    assert extract_homepage("", "https://x.com").is_empty()
    assert extract_homepage("<not really html", "https://x.com") is not None
