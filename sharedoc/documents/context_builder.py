from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..db.repository import ContractBundle


MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

COUNT_WORDS_GENITIVE = {
    0: "нуля",
    1: "одного",
    2: "двух",
    3: "трех",
    4: "четырех",
    5: "пяти",
    6: "шести",
    7: "семи",
    8: "восьми",
    9: "девяти",
    10: "десяти",
    11: "одиннадцати",
    12: "двенадцати",
    13: "тринадцати",
    14: "четырнадцати",
    15: "пятнадцати",
    16: "шестнадцати",
    17: "семнадцати",
    18: "восемнадцати",
    19: "девятнадцати",
    20: "двадцати",
}

ONES_MALE = [
    "",
    "один",
    "два",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
]

ONES_FEMALE = [
    "",
    "одна",
    "две",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
]

TEENS = [
    "десять",
    "одиннадцать",
    "двенадцать",
    "тринадцать",
    "четырнадцать",
    "пятнадцать",
    "шестнадцать",
    "семнадцать",
    "восемнадцать",
    "девятнадцать",
]

TENS = [
    "",
    "",
    "двадцать",
    "тридцать",
    "сорок",
    "пятьдесят",
    "шестьдесят",
    "семьдесят",
    "восемьдесят",
    "девяносто",
]

HUNDREDS = [
    "",
    "сто",
    "двести",
    "триста",
    "четыреста",
    "пятьсот",
    "шестьсот",
    "семьсот",
    "восемьсот",
    "девятьсот",
]


def format_date_dotted(value: date | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d.%m.%Y") + " г."


def format_date_words(value: date | None) -> str:
    if value is None:
        return ""
    month = MONTHS_GENITIVE[value.month]
    return f"{value.day} {month} {value.year} г."


def format_date_contract(value: date | None) -> str:
    if value is None:
        return ""
    month = MONTHS_GENITIVE[value.month]
    return f"«{value.day:02d}» {month} {value.year} г."


def format_money(amount: Decimal | int | float | None) -> str:
    if amount is None:
        return ""
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = f"{value:,.2f}"
    return text.replace(",", " ").replace(".", ",")


def choose_plural(number: int, forms: tuple[str, str, str]) -> str:
    n = abs(number) % 100
    n1 = n % 10

    if 10 < n < 20:
        return forms[2]
    if n1 == 1:
        return forms[0]
    if 1 < n1 < 5:
        return forms[1]
    return forms[2]


def triplet_to_words(number: int, feminine: bool = False) -> list[str]:
    if not 0 <= number <= 999:
        raise ValueError("Ожидается число от 0 до 999")

    result: list[str] = []
    hundreds = number // 100
    tens_units = number % 100
    tens = tens_units // 10
    units = tens_units % 10

    if hundreds:
        result.append(HUNDREDS[hundreds])

    if 10 <= tens_units <= 19:
        result.append(TEENS[tens_units - 10])
        return result

    if tens >= 2:
        result.append(TENS[tens])

    if units:
        result.append(ONES_FEMALE[units] if feminine else ONES_MALE[units])

    return result


def int_to_russian_words(number: int) -> str:
    if number == 0:
        return "ноль"

    if number < 0:
        return "минус " + int_to_russian_words(abs(number))

    parts: list[str] = []

    billions = number // 1_000_000_000
    millions = (number // 1_000_000) % 1000
    thousands = (number // 1000) % 1000
    rest = number % 1000

    if billions:
        parts.extend(triplet_to_words(billions))
        parts.append(choose_plural(billions, ("миллиард", "миллиарда", "миллиардов")))

    if millions:
        parts.extend(triplet_to_words(millions))
        parts.append(choose_plural(millions, ("миллион", "миллиона", "миллионов")))

    if thousands:
        parts.extend(triplet_to_words(thousands, feminine=True))
        parts.append(choose_plural(thousands, ("тысяча", "тысячи", "тысяч")))

    if rest:
        parts.extend(triplet_to_words(rest))

    return " ".join(parts)


def money_to_full_text(amount: Decimal | int | float | None) -> str:
    if amount is None:
        return ""

    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rubles = int(value)
    kopeks = int((value - Decimal(rubles)) * 100)

    rubles_words = int_to_russian_words(rubles).capitalize()
    ruble_form = choose_plural(rubles, ("рубль", "рубля", "рублей"))

    return f"{format_money(value)} ({rubles_words}) {ruble_form} {kopeks:02d} копеек"


def listeners_count_text(count: int) -> str:
    word = COUNT_WORDS_GENITIVE.get(count)
    if word is None:
        return str(count)
    return f"{count} ({word})"


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^\w\-_.А-Яа-яЁё ]+", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "_", value.strip())
    return value[:120] if value else "document"


def build_output_filename(template_key: str, contract: dict[str, Any]) -> str:
    short_name = sanitize_filename(contract.get("company_short_name", ""))
    contract_number = sanitize_filename(contract.get("contract_number", ""))

    prefix_map = {
        "scientific_guidance": "scientific_guidance",
        "qualification": "qualification",
        "contract_offer": "contract_offer",
    }
    prefix = prefix_map[template_key]
    return f"{prefix}_{contract_number}_{short_name}.docx"


def _address_part(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def build_full_address(contract: dict[str, Any]) -> str:
    postal_code = _address_part(contract.get("address_postal_code"))
    region = _address_part(contract.get("address_region"))
    city = _address_part(contract.get("address_city"))
    settlement = _address_part(contract.get("address_settlement"))
    street = _address_part(contract.get("address_street"))
    house = _address_part(contract.get("address_house"))
    building = _address_part(contract.get("address_building"))
    premises = _address_part(contract.get("address_premises"))

    parts: list[str] = []

    if postal_code:
        parts.append(postal_code)
    if region:
        parts.append(region)
    if city:
        parts.append(f"г. {city}")
    if settlement:
        parts.append(settlement)
    if street:
        parts.append(f"ул. {street}")
    if house:
        parts.append(f"д. {house}")
    if building:
        parts.append(building)
    if premises:
        parts.append(f"помещ. {premises}")

    return ", ".join(parts)


def build_mailing_address(contract: dict[str, Any]) -> str:
    postal_code = _address_part(contract.get("address_postal_code"))
    region = _address_part(contract.get("address_region"))
    city = _address_part(contract.get("address_city"))
    street = _address_part(contract.get("address_street"))
    house = _address_part(contract.get("address_house"))
    building = _address_part(contract.get("address_building"))

    parts: list[str] = []

    if postal_code:
        parts.append(postal_code)
    if region:
        parts.append(region)
    if city:
        parts.append(f"г. {city}")
    if street:
        parts.append(f"ул. {street}")
    if house:
        parts.append(f"д. {house}")
    if building:
        parts.append(building)

    return ", ".join(parts)


def build_context(bundle: ContractBundle, template_key: str) -> dict[str, Any]:
    contract = bundle.contract
    students = bundle.students

    unit_price = contract["unit_price"]
    total_price = contract["total_price"]
    contract_date = contract["contract_date"]
    training_start_date = contract["training_start_date"]
    training_end_date = contract["training_end_date"]
    reply_deadline = contract["reply_deadline"]

    full_address = build_full_address(contract)
    mailing_address = build_mailing_address(contract)

    computed_listeners_count = len(students) if students else int(contract["listeners_count"] or 0)
    listeners_count_value = int(contract["listeners_count"] or computed_listeners_count)

    if (
        total_price is None
        or Decimal(str(total_price)) == Decimal("0")
    ) and unit_price is not None and listeners_count_value > 0:
        total_price = Decimal(str(unit_price)) * listeners_count_value

    context = {
        # клиент
        "company_full_name": contract["company_full_name"] or "",
        "company_short_name": contract["company_short_name"] or "",
        "company_ogrn": contract["ogrn"] or "",
        "company_inn": contract["inn"] or "",
        "company_kpp": contract["kpp"] or "",
        "company_bank_account": contract["bank_account"] or "",
        "company_corr_account": contract["corr_account"] or "",
        "company_bik": contract["bik"] or "",
        "company_bank_name": contract["bank_name"] or "",
        "company_payment_recipient": contract["payment_recipient"] or "",

        # адреса для шаблонов
        "company_legal_address": full_address,
        "company_postal_address": full_address,
        "company_mailing_address": mailing_address,

        # представитель
        "representative_short_fio_dative": contract["short_fio_dative"] or "",
        "representative_email": contract["representative_email"] or "",
        "representative_name_patronymic": contract["name_patronymic"] or "",
        "representative_position_genitive": contract["position_genitive"] or "",
        "representative_full_name_genitive": contract["full_name_genitive"] or "",
        "representative_position_nominative": contract["position_nominative"] or "",
        "representative_initials": contract["initials"] or "",
        "representative_basis": contract["basis"] or "",

        # программа / договор
        "program_name": contract["program_name"] or "",
        "training_start_date_text": format_date_dotted(training_start_date),
        "training_end_date_text": format_date_dotted(training_end_date),
        "program_hours": contract["program_hours"] or 0,
        "unit_price_text": f"{format_money(unit_price)} руб.",
        "unit_price_text_full": money_to_full_text(unit_price),
        "reply_deadline_text": format_date_dotted(reply_deadline),
        "ikz": contract["ikz"] or "",
        "contract_number": contract["contract_number"] or "",
        "contract_date_text": format_date_contract(contract_date),
        "listeners_count": listeners_count_value,
        "listeners_count_text": listeners_count_text(listeners_count_value),
        "total_price_text_full": money_to_full_text(total_price),

        # контакт по договору
        "company_contact_full_name": contract["contact_full_name"] or "",
        "company_contact_phone": contract["contact_phone"] or "",
        "company_contact_email": contract["contact_email"] or "",

        # слушатели
        "students": [
            {
                "row_no": student.get("row_no", index + 1),
                "full_name": student["full_name"] or "",
                "phone": student["phone"] or "",
                "email": student["email"] or "",
            }
            for index, student in enumerate(students)
        ],
    }

    if template_key == "scientific_guidance":
        context["training_start_date_text"] = format_date_dotted(training_start_date)
        context["training_end_date_text"] = format_date_dotted(training_end_date)
        context["reply_deadline_text"] = format_date_dotted(reply_deadline)

    elif template_key == "qualification":
        context["training_start_date_text"] = format_date_dotted(training_start_date)
        context["training_end_date_text"] = format_date_dotted(training_end_date)

    elif template_key == "contract_offer":
        context["training_start_date_text"] = format_date_words(training_start_date)
        context["training_end_date_text"] = format_date_words(training_end_date)

    return context