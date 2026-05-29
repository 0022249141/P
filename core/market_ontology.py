"""
core/market_ontology.py
Institutional market ontology with bilingual explanations.
Definitions use inference-based language; they do not claim direct observation of dealer inventory.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List

SUPPORTED_LANGUAGES = {"en", "fa"}


class OntologyConcept(str, Enum):
    LIQUIDITY = "liquidity"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    INDUCEMENT = "inducement"
    TRANSFER = "transfer"
    DELIVERY = "delivery"
    COMMITMENT = "commitment"
    REPRICING = "repricing"
    MANIPULATION = "manipulation"
    DISPLACEMENT = "displacement"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"


ONTOLOGY: Dict[str, Dict[str, str]] = {
    "liquidity": {"en": "Liquidity represents observable price zones where stop orders or breakout participation may cluster.", "fa": "نقدینگی به نواحی قابل مشاهده‌ای گفته می‌شود که احتمال تجمع حدضررها یا ورودهای شکست در آن‌ها وجود دارد."},
    "liquidity_sweep": {"en": "A liquidity sweep is an inferred event where price trades through a mapped level and then shows rejection or reclaim behavior.", "fa": "جاروب نقدینگی رخدادی استنباطی است که در آن قیمت از سطح نقدینگی عبور می‌کند و سپس نشانه‌های رد قیمت یا بازپس‌گیری سطح را نشان می‌دهد."},
    "inducement": {"en": "Inducement is an inferred setup where price action appears to attract participation before a higher-probability delivery path.", "fa": "القای نقدینگی وضعیتی استنباطی است که در آن رفتار قیمت مشارکت یا حدضرر معامله‌گران را پیش از مسیر محتمل‌تر تحویل جذب می‌کند."},
    "transfer": {"en": "Transfer is an inferred rotation between internal liquidity zones before directional commitment is resolved.", "fa": "انتقال فازی استنباطی است که قیمت میان نواحی نقدینگی داخلی گردش می‌کند و تعهد جهت‌دار هنوز قطعی نشده است."},
    "delivery": {"en": "Delivery is a directional repricing sequence toward external liquidity after commitment evidence strengthens.", "fa": "تحویل یک توالی قیمت‌گذاری جهت‌دار به سمت نقدینگی بیرونی است که پس از تقویت شواهد تعهد شکل می‌گیرد."},
    "commitment": {"en": "Commitment is inferred when displacement, reclaim behavior, and target alignment support continuation toward a liquidity objective.", "fa": "تعهد زمانی استنباط می‌شود که جابجایی، بازپس‌گیری سطح و همسویی هدف نقدینگی از ادامه مسیر حمایت کنند."},
    "repricing": {"en": "Repricing is an observable adjustment in price that may seek new counterparties or liquidity balance.", "fa": "قیمت‌گذاری مجدد تعدیل قابل مشاهده قیمت است که می‌تواند برای جذب طرف مقابل یا متعادل‌سازی نقدینگی رخ دهد."},
    "manipulation": {"en": "Manipulation is an inferred false directional move, often around liquidity, before the market chooses a more durable path.", "fa": "دستکاری یک حرکت جهت‌دار کاذب و استنباطی، غالباً پیرامون نقدینگی، پیش از انتخاب مسیر پایدارتر بازار است."},
    "displacement": {"en": "Displacement is a strong directional movement with improved range/body efficiency that may confirm repricing intent.", "fa": "جابجایی حرکت جهت‌دار قوی با کارایی بهتر بدنه/رنج است که می‌تواند نیت قیمت‌گذاری مجدد را تأیید کند."},
    "accumulation": {"en": "Accumulation is an inferred regime where downside absorption and constrained range behavior suggest potential long-side inventory formation.", "fa": "انباشت رژیمی استنباطی است که جذب نقدینگی سمت فروش و رفتار محدود قیمت احتمال شکل‌گیری تمایل خرید را نشان می‌دهد."},
    "distribution": {"en": "Distribution is an inferred regime where upside absorption and failure to continue higher suggest potential inventory rotation or unloading.", "fa": "توزیع رژیمی استنباطی است که جذب نقدینگی سمت خرید و ناتوانی در ادامه صعود احتمال چرخش یا تخلیه موجودی را نشان می‌دهد."},
}


def _concept_value(concept: str | OntologyConcept) -> str:
    return concept.value if isinstance(concept, OntologyConcept) else str(concept)


def get_ontology_text(concept: str | OntologyConcept, lang: str = "en") -> str:
    key = _concept_value(concept)
    item = ONTOLOGY.get(key)
    if not item:
        return "Definition not found." if lang != "fa" else "تعریف یافت نشد."
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    return item.get(lang) or item.get("en") or "Definition not found."


def list_concepts() -> List[str]:
    return list(ONTOLOGY.keys())


def concept_exists(concept: str | OntologyConcept) -> bool:
    return _concept_value(concept) in ONTOLOGY


def get_all_ontology(lang: str = "fa") -> Dict[str, str]:
    return {key: get_ontology_text(key, lang) for key in ONTOLOGY}
