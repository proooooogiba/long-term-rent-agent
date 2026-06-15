from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from src.agent.domain_types import infer_housing_type
from src.agent.message_understanding import IntakeExtraction, RouterDecision
from src.agent.replanner import ReplanningAssessment


KNOWN_CITIES = [
    "Алматы",
    "Ереван",
    "Ташкент",
    "Минск",
    "Баку",
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Екатеринбург",
]

FIELD_LABELS = {
    "city": "город",
    "move_in_date": "дату переезда",
    "monthly_budget": "месячный бюджет",
    "household_composition": "состав домохозяйства",
    "rooms_or_housing_type": "комнаты или тип жилья",
    "office_zone_or_commute_target": "офисную локацию или лимит времени в пути",
}


class DemoStructuredLLM:
    """Deterministic demo backend for offline presentations and screenshot generation."""

    def extract_json(self, system_prompt: str, user_prompt: str, schema):
        if schema is RouterDecision:
            return schema.model_validate(self._route(user_prompt))
        if schema is IntakeExtraction:
            return schema.model_validate(self._extract_intake(user_prompt))
        if schema is ReplanningAssessment:
            return schema.model_validate(self._replanning_assessment(user_prompt))

        schema_name = schema.__name__
        if schema_name == "RecommendationAnswerSections":
            return schema.model_validate(self._recommendation_sections(user_prompt))
        if schema_name == "ClarificationAnswerSections":
            return schema.model_validate(self._clarification_sections(user_prompt))
        if schema_name == "EscalationAnswerSections":
            return schema.model_validate(self._escalation_sections(user_prompt))
        if schema_name == "InfoAnswerSections":
            return schema.model_validate(self._info_sections(user_prompt))

        raise RuntimeError(f"DemoStructuredLLM does not support schema `{schema_name}`.")

    def _route(self, user_prompt: str) -> dict[str, Any]:
        message = self._extract_user_message(user_prompt).lower()
        if any(token in message for token in ["сниз", "уменьш", "подним", "увелич", "теперь", "вместо", "переносим"]):
            return {"intent": "replanning", "rationale": "Detected constraint change in follow-up message."}
        if any(token in message for token in ["депозит", "коммунал", "правил", "регистрац", "как оформить", "что по документ"]):
            return {"intent": "info", "rationale": "Detected informational policy-style question."}
        return {"intent": "search", "rationale": "Default demo route goes to housing search."}

    def _extract_intake(self, user_prompt: str) -> dict[str, Any]:
        message = self._extract_user_message(user_prompt)
        lowered = message.lower()
        result: dict[str, Any] = {
            "center_preference": "unspecified",
            "office_dependency": False,
        }

        city = next((item for item in KNOWN_CITIES if item.lower() in lowered), None)
        if city:
            result["city"] = city

        if move_in := self._extract_date(message):
            result["move_in_date"] = move_in.isoformat()

        if budget := self._extract_budget(message):
            result["monthly_budget"] = budget
        if budget_currency := self._extract_budget_currency(message):
            result["budget_currency"] = budget_currency

        if rooms := self._extract_rooms(message):
            result["rooms_min"] = rooms
        if housing_type := self._extract_housing_type(message):
            result["housing_type"] = housing_type

        if commute := self._extract_commute(message):
            result["max_commute_minutes"] = commute
            result["office_dependency"] = True

        if "офис" in lowered or "дорог" in lowered or "в пути" in lowered:
            result["office_dependency"] = True

        if "мебли" in lowered:
            result["furnished"] = "без мебели" not in lowered
        if "без мебели" in lowered:
            result["furnished"] = False

        if "лифт" in lowered:
            result["elevator"] = "без лифта" not in lowered

        if "центр не обязател" in lowered or "не в центре" in lowered or "без центра" in lowered:
            result["center_preference"] = "center_not_required"
        elif "в центре" in lowered or "поближе к центру" in lowered or "центр важен" in lowered:
            result["center_preference"] = "prefer_center"

        if adults := self._extract_adults(lowered):
            result["adults"] = adults
        elif "семья" in lowered and "двое взрослых" not in lowered:
            result["adults"] = 2

        if children := self._extract_children(message):
            result["children"] = children

        pets = self._extract_pets(lowered)
        if pets:
            result["pets"] = pets

        if "загран" in lowered and any(token in lowered for token in ["нет", "без"]):
            result["has_passport"] = False
            result["document_status"] = "incomplete_docs"
        elif "документы готовы" in lowered:
            result["document_status"] = "complete"

        if "работодатель помогает" in lowered:
            result["employer_support"] = True

        return result

    def _replanning_assessment(self, user_prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(user_prompt)
        changes = context.get("changed_constraints") or {}
        dropped_ids = context.get("dropped_listing_ids") or []
        impact_tags: list[str] = []
        notes: list[str] = []

        if "city" in changes:
            impact_tags.append("city_reset")
            notes.append("Из-за смены города shortlist пересобран почти с нуля.")
        if "monthly_budget" in changes:
            old = changes["monthly_budget"].get("old")
            new = changes["monthly_budget"].get("new")
            if old is not None and new is not None and new < old:
                impact_tags.append("budget_tightened")
                notes.append("Бюджет стал строже, поэтому часть прежних вариантов могла выпасть.")
            elif old is not None and new is not None and new > old:
                impact_tags.append("budget_relaxed")
                notes.append("Бюджет вырос, поэтому агент проверил более широкий пул вариантов.")
        if "move_in_date" in changes:
            impact_tags.append("availability_window_changed")
            notes.append("Срок въезда изменился, поэтому заново проверена доступность объектов.")
        if "max_commute_minutes" in changes or "preferred_districts" in changes:
            impact_tags.append("commute_constraint_changed")
            notes.append("Изменились требования к локации или времени в пути.")
        if "household" in changes:
            impact_tags.append("household_changed")
            notes.append("Состав домохозяйства изменился, поэтому пересчитаны ограничения по жилью.")
        if any("pet" in key for key in changes):
            impact_tags.append("pet_policy_changed")
            notes.append("Уточнение по питомцам влияет на допустимые варианты аренды.")
        if dropped_ids:
            impact_tags.append("shortlist_changed")
            notes.append("Часть прежних вариантов исчезла из топа после пересборки шортлиста.")

        return {"impact_tags": impact_tags, "notes": notes}

    def _recommendation_sections(self, user_prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(user_prompt)
        ranked = context.get("ranked_listings") or []
        warnings = ((context.get("verification_result") or {}).get("warnings")) or []
        replanning_notes = context.get("replanning_notes") or []
        best = ranked[0] if ranked else None
        if best:
            summary = (
                f"Лучший текущий вариант — {best['listing_id']} в районе {best['district_name']} "
                f"за {best['monthly_rent']:.0f} {best['currency']} в месяц."
            )
        else:
            summary = "Подбор выполнен, но для сильного shortlist стоит уточнить дополнительные ограничения."
        return {
            "summary": " ".join([summary, *replanning_notes[:1]]).strip(),
            "important_notes": warnings[:4],
            "alternatives": [
                f"{item['listing_id']}: {item['monthly_rent']:.0f} {item['currency']}/мес, {item['district_name']}"
                for item in ranked[1:3]
            ],
            "clarification_lines": ((context.get("verification_result") or {}).get("required_user_clarifications")) or [],
        }

    def _clarification_sections(self, user_prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(user_prompt)
        raw_questions = (
            ((context.get("verification_result") or {}).get("required_user_clarifications")) or context.get("missing_fields") or []
        )
        rendered = [FIELD_LABELS.get(item, item) for item in raw_questions]
        return {
            "preface": "Чтобы продолжить подбор, мне нужно уточнить несколько вещей:",
            "questions": rendered,
        }

    def _escalation_sections(self, user_prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(user_prompt)
        verification = context.get("verification_result") or {}
        services = context.get("relocation_services") or []
        preparations = [
            f"{item['name']}: {item['description']}"
            for item in services[:2]
        ]
        if not preparations:
            preparations = ["Подготовить документы, подтверждение дохода и уточнить легальный маршрут въезда."]
        return {
            "reason_summary": "Кейс лучше передать человеку из-за документных или юридически чувствительных ограничений.",
            "reasons": verification.get("warnings") or verification.get("failed_checks") or ["Нужна дополнительная ручная проверка."],
            "preparations": preparations,
        }

    def _info_sections(self, user_prompt: str) -> dict[str, Any]:
        context = self._extract_context_json(user_prompt)
        chunks = context.get("retrieved_policy_chunks") or []
        details = [item.get("text", "")[:180] for item in chunks[:3] if item.get("text")]
        if not details:
            details = ["Ответ собран на основе базы правил аренды и relocation-заметок проекта."]
        return {
            "summary": "Подготовил краткий справочный ответ по правилам аренды и релокации.",
            "details": details,
            "case_impact": ["Для финального решения всё равно стоит проверить актуальные официальные правила и условия арендодателя."],
        }

    def _extract_user_message(self, payload: str) -> str:
        message_match = re.search(r"User message:\n(.*?)(?:\n\n|$)", payload, flags=re.DOTALL)
        if message_match:
            return message_match.group(1).strip()

        context = self._extract_context_json(payload)
        if isinstance(context.get("user_message"), str):
            return str(context["user_message"])
        return payload.strip()

    def _extract_context_json(self, payload: str) -> dict[str, Any]:
        match = re.search(r"Context JSON:\n(\{.*\})", payload, flags=re.DOTALL)
        if not match:
            return {}
        return json.loads(match.group(1))

    def _extract_date(self, message: str) -> date | None:
        iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
        if iso_match:
            return date.fromisoformat(iso_match.group(1))
        dotted_match = re.search(r"\b(\d{2})\.(\d{2})\.(20\d{2})\b", message)
        if dotted_match:
            day, month, year = dotted_match.groups()
            return date(int(year), int(month), int(day))
        return None

    def _extract_budget(self, message: str) -> float | None:
        lowered = message.lower()

        explicit_budget = re.search(
            r"(?:бюджет(?:ом)?(?:\s*до)?|до)\s*(\d[\d\s]{2,})\s*(?:usd|доллар(?:ов)?|eur|евро|руб(?:лей)?|₽)?\b",
            lowered,
        )
        if explicit_budget:
            return float(explicit_budget.group(1).replace(" ", ""))

        currency_amount = re.search(
            r"\b(\d{3,6})\s*(?:usd|доллар(?:ов)?|eur|евро|руб(?:лей)?|₽)\b",
            lowered,
        )
        if currency_amount:
            return float(currency_amount.group(1))

        generic_candidates = re.findall(r"(?<![.\-/])\b(\d{3,6})\b(?![.\-/])", lowered)
        if not generic_candidates:
            return None
        return float(generic_candidates[-1].replace(" ", ""))

    def _extract_budget_currency(self, message: str) -> str | None:
        lowered = message.lower()
        if any(token in lowered for token in ["usd", "$", "доллар"]):
            return "USD"
        if any(token in lowered for token in ["eur", "€", "евро"]):
            return "EUR"
        if any(token in lowered for token in ["rub", "rur", "₽", "руб"]):
            return "RUB"
        if any(token in lowered for token in ["kzt", "₸", "тенге"]):
            return "KZT"
        if any(token in lowered for token in ["amd", "֏", "драм"]):
            return "AMD"
        if any(token in lowered for token in ["byn", "белруб"]):
            return "BYN"
        if any(token in lowered for token in ["uzs", "сум"]):
            return "UZS"
        return None

    def _extract_rooms(self, message: str) -> int | None:
        match = re.search(r"\b(\d)\s*(?:-|–)?\s*(?:комн|комнат)", message.lower())
        if match:
            return int(match.group(1))
        if "студ" in message.lower():
            return 1
        return None

    def _extract_housing_type(self, message: str) -> str | None:
        return infer_housing_type(message)

    def _extract_adults(self, lowered_message: str) -> int | None:
        if re.search(r"(?:\bпара\b|для пары|двое взрослых|2 взрослых)", lowered_message):
            return 2
        if re.search(r"(?:1 взросл|один взросл|для одного)", lowered_message):
            return 1
        return None

    def _extract_commute(self, message: str) -> int | None:
        match = re.search(r"(?:до|не больше|не дольше)\s*(\d{1,3})\s*мин", message.lower())
        if match:
            return int(match.group(1))
        return None

    def _extract_children(self, message: str) -> int | None:
        match = re.search(r"(\d)\s*(?:дет|ребенк|ребёнк)", message.lower())
        if match:
            return int(match.group(1))
        return 1 if "с ребёнком" in message.lower() or "с ребенком" in message.lower() else None

    def _quantity_from_token(self, token: str | None) -> int:
        if not token:
            return 1
        normalized = token.strip().lower()
        if normalized.isdigit():
            return int(normalized)
        return {
            "один": 1,
            "одна": 1,
            "одного": 1,
            "одной": 1,
            "две": 2,
            "два": 2,
            "двух": 2,
            "двумя": 2,
            "три": 3,
            "трех": 3,
            "трёх": 3,
        }.get(normalized, 1)

    def _extract_pets(self, lowered_message: str) -> list[str]:
        pets: list[str] = []
        pet_patterns = [
            ("cat", r"(?:(\d+|один|одна|одного|одной|две|два|двух|двумя|три|трех|трёх)\s+)?(?:кот(?:ы|а|ов)?|кошк(?:а|и|у|ой|е|ами|ах)?|cat)\b"),
            ("dog", r"(?:(\d+|один|одна|одного|одной|две|два|двух|двумя|три|трех|трёх)\s+)?(?:собак(?:а|и|у|ой|е|ами|ах)?|пёс|пес|пса|псов|dog)\b"),
        ]
        for pet_kind, pattern in pet_patterns:
            for match in re.finditer(pattern, lowered_message):
                pets.extend([pet_kind] * self._quantity_from_token(match.group(1)))
        return pets
