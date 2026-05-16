import pycountry
from babel import Locale
import re

langs = {'en': 'en', 'ar': 'ar', 'zh': 'zh', 'ru': 'ru', 'tr': 'tr', 'es': 'es', 'fa': 'fa', 'bn': 'bn', 'uz': 'uz'}
locales = {k: Locale.parse(v) for k, v in langs.items()}

out = 'const COUNTRY_NAMES = {\n'
for country in pycountry.countries:
    iso = country.alpha_2
    translations = []
    for lang, loc in locales.items():
        name = loc.territories.get(iso, country.name)
        if name:
            name = name.replace('\'', '\\\'').replace('\"', '\\\"')
        translations.append(f'"{lang}":"{name}"')
    out += f'            "{iso}":{{{ ",".join(translations) }}},\n'
out += '        };'

for filepath in ['templates/seller.html', 'templates/store.html']:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Regex to match the existing COUNTRY_NAMES definition
    # It starts with "const COUNTRY_NAMES = {" and ends with "};"
    new_content = re.sub(r'const COUNTRY_NAMES = \{[\s\S]*?\};', out, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
print("Updated seller.html and store.html with 249+ countries!")
