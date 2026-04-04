from bs4 import BeautifulSoup
import re

html = """
<table>
    <thead><tr><th>Nome</th><th>Valor</th></tr></thead>
    <tbody>
        <tr><td>Item 1</td><td>R$ 10,00</td></tr>
        <tr class="total"><td>Total da soma</td><td>-R$ 5,00</td></tr>
    </tbody>
</table>
"""
soup = BeautifulSoup(html, "html.parser")
table = soup.find("table")

# 4. Row numbers: automatic row number column
# Check rows
for row in table.find_all("tr"):
    # highlight total row
    text = row.get_text().lower()
    if any(word in text for word in ['total', 'sobra', 'resultado', 'saldo']):
        # Apply highlight color
        # Find numeric values
        tds = row.find_all(["td", "th"])
        for td in tds:
            # simple check for negative
            if "-" in td.get_text():
                td['style'] = "color: #ff4444;"
            else:
                td['style'] = "color: #44ff44;"

# insert row numbers
# find thead tr
thead = table.find("thead")
if thead:
    for tr in thead.find_all("tr"):
        new_th = soup.new_tag("th")
        new_th.string = "#"
        tr.insert(0, new_th)

tbody = table.find("tbody") or table
idx = 1
for tr in tbody.find_all("tr"):
    if tr.parent.name == "thead": continue
    if not tr.find("td") and tr.find("th"): continue # header row in tbody?
    new_td = soup.new_tag("td")
    new_td.string = str(idx)
    tr.insert(0, new_td)
    idx += 1

print(soup.prettify())
