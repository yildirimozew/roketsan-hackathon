# ============================================================
# AR-GE ID     : ALTYAPI
# Başlık       : arge_m paket girişi ve adım klasörü takma adları
# Akış adımı   : tümü (klasörler ajan akışının 8 adımına göre sıralı)
# Durum        : test edildi
# Amaç         : "00_ortak" gibi rakamla başlayan klasör adları Python import satırında
#                yazılamaz; her klasörü okunur bir takma adla (arge_m.ortak, arge_m.risk ...) kaydeder.
# Kanıt        : -
# Çalıştırma   : arge/ klasöründen: python -m arge_m.run  |  python -m pytest arge_m/tests -q
# Entegrasyon  : Ana koda taşınmaz; yalnızca AR-GE klasörünün düzeni içindir.
# Sınırlar     : Modülleri her zaman takma adla içe aktarın (arge_m.ortak.data), rakamlı adla değil;
#                ikisi karışırsa aynı sınıfın iki kopyası oluşur.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Mustafa's R&D workspace, one folder per step of the SENTINEL agent flow (see ARGE_M.md)."""

import importlib
import re
import sys
from pathlib import Path

_STEP_DIR = re.compile(r"^\d\d_(?P<alias>[a-z_]+)$")

for _folder in sorted(Path(__file__).parent.iterdir()):
    _m = _STEP_DIR.match(_folder.name)
    if _m and (_folder / "__init__.py").exists():
        _module = importlib.import_module(f"{__name__}.{_folder.name}")
        sys.modules[f"{__name__}.{_m['alias']}"] = _module
        setattr(sys.modules[__name__], _m["alias"], _module)
