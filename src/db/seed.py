from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "relocation" / "relocation.sqlite"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _j(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


COUNTRIES = [
    {
        "country_id": "KZ",
        "name": "Казахстан",
        "relocation_by_internal_passport": 1,
        "residence_orientation": "Официальный маршрут обычно начинается с временного проживания и регистрации; для разрешения на постоянное проживание eGov отдельно подчёркивает подтверждение платёжеспособности.",
        "citizenship_orientation": "Официальный общий порядок: не менее 5 лет постоянного проживания либо 3 года брака с гражданином Казахстана; двойное гражданство в общем случае не допускается.",
        "cost_of_living_single_range": "450-700 USD",
        "cost_of_living_family_range": "900-1400 USD",
        "primary_city": "Алматы",
        "notes": _j([
            "В базовом проектном сценарии допускается въезд по внутреннему паспорту, но конкретный въездной режим нужно перепроверять под гражданство пользователя.",
            "Официальный старт по документам: temporary residence permit, затем отдельный маршрут на постоянное проживание через органы внутренних дел.",
            "Источник (temporary residence permit): https://egov.kz/cms/en/services/for_foreigners/00203002_mvd",
            "Источник (permanent residence permit): https://egov.kz/cms/en/articles/for_foreigners/vid_na_jitelstvo",
            "Источник (citizenship): https://egov.kz/cms/en/articles/for_foreigners/how_to_become_kz_citizen",
            "Источник (double citizenship): https://egov.kz/cms/en/articles/for_foreigners/double_citizenship",
        ]),
    },
    {
        "country_id": "AM",
        "name": "Армения",
        "relocation_by_internal_passport": 1,
        "residence_orientation": "Официальный сервис Армении выделяет temporary, permanent и special residence status; в публичном описании встречаются основания по происхождению, семье, бизнесу, работе и образованию.",
        "citizenship_orientation": "По публичному описанию закона о гражданстве основной маршрут натурализации опирается на 3 года постоянного проживания, знание армянского языка и Конституции; для ряда категорий действует упрощение.",
        "cost_of_living_single_range": "500-800 USD",
        "cost_of_living_family_range": "1000-1600 USD",
        "primary_city": "Ереван",
        "notes": _j([
            "Близость к центру заметно увеличивает цену, но миграционный маршрут для проекта удобнее вести через migration.e-gov.am и ARLIS.",
            "Для employment-based кейсов полезно отдельно смотреть разрешение на работу и его связку с residence status.",
            "Источник (residence status): https://migration.e-gov.am/en/service/residency_application/info",
            "Источник (work permits): https://migration.e-gov.am/en/service/work_permits/info",
            "Источник (citizenship application): https://migration.e-gov.am/en/service/citizenship_application/info",
            "Источник (citizenship law): https://www.arlis.am/hy/acts/219000",
        ]),
    },
    {
        "country_id": "UZ",
        "name": "Узбекистан",
        "relocation_by_internal_passport": 0,
        "residence_orientation": "Официальный маршрут обычно начинается с временной регистрации после прибытия; далее permanent residence оформляется через подразделения migration and citizenship registration, а само разрешение выдают на 5 лет, но не дольше срока действия паспорта.",
        "citizenship_orientation": "Официальный ориентир МВД Узбекистана: отказ от иного гражданства, 5 лет непрерывного проживания после получения вида на жительство, законный доход и достаточное владение государственным языком.",
        "cost_of_living_single_range": "400-650 USD",
        "cost_of_living_family_range": "850-1300 USD",
        "primary_city": "Ташкент",
        "notes": _j([
            "В базовом проектном сценарии требуется загранпаспорт; временная регистрация после въезда идёт отдельным слоем до вопросов ПМЖ и гражданства.",
            "Для срочной релокации разумно разделять временную регистрацию, жильё на стартовый период и долгосрочный маршрут по документам.",
            "Источник (temporary stay and residence permit overview): https://oldmy.gov.uz/en/tourism",
            "Источник (citizenship / residence certificate application): https://gov.uz/en/iiv/pages/fuqarolik-yoki-yashash-uchun-guvohnomani-olish-uchun-ariza-berish-tartibi-malumoti",
        ]),
    },
    {
        "country_id": "BY",
        "name": "Беларусь",
        "relocation_by_internal_passport": 1,
        "residence_orientation": "Официальный стартовый маршрут обычно начинается с регистрации временного пребывания; основания для постоянного проживания публично описываются через семью, длительное проживание, работу, инвестиции и другие специальные категории.",
        "citizenship_orientation": "Публичный ориентир официальных белорусских источников: решение о гражданстве оформляется указом Президента, а в типовом кейсе фигурируют 5 и более лет проживания и знание одного из государственных языков.",
        "cost_of_living_single_range": "400-650 USD",
        "cost_of_living_family_range": "850-1300 USD",
        "primary_city": "Минск",
        "notes": _j([
            "Рынок чувствителен к документам и формату занятости, поэтому для проекта лучше хранить отдельно временную регистрацию, ПМЖ и гражданство.",
            "Для офисного графика важен баланс метро и стоимости, но миграционные правила стоит начинать с MFA/portal.gov.by и подразделений citizenship and migration.",
            "Источник (registration of temporary stay): https://mfa.gov.by/en/visa/registration/",
            "Источник (permanent residence permit overview): https://www.brest.brest-region.gov.by/en/news-en/view/how-can-a-foreigner-obtain-a-permanent-residence-permit-in-the-republic-of-belarus-2000004657",
            "Источник (citizenship public orientation): https://president.gov.by/en/events/podpisan-ukaz-o-prieme-v-belorusskoe-grazdanstvo-230-celovek-1776410899",
        ]),
    },
    {
        "country_id": "AZ",
        "name": "Азербайджан",
        "relocation_by_internal_passport": 0,
        "residence_orientation": "Официальный маршрут идёт через State Migration Service: temporary residence permit обычно выдаётся до 1 года, а permanent residence в типовом кейсе рассматривается после как минимум 2 лет временного проживания на подходящем основании.",
        "citizenship_orientation": "По State Migration Service общий маршрут гражданства опирается на 5 лет непрерывного законного и постоянного проживания, законный доход и документ о знании государственного языка.",
        "cost_of_living_single_range": "450-700 USD",
        "cost_of_living_family_range": "900-1450 USD",
        "primary_city": "Баку",
        "notes": _j([
            "Центральные районы быстро выходят за базовый семейный бюджет, а по документам лучше разделять temporary residence, permanent residence и citizenship issues.",
            "Для pet-friendly семейных вариантов часто нужен компромисс по времени в пути, но миграционный первоисточник — State Migration Service Azerbaijan.",
            "Источник (temporary and permanent residence permits): https://migration.gov.az/en/page/73",
            "Источник (citizenship of the Republic of Azerbaijan): https://migration.gov.az/en/useful/45",
            "Источник (citizenship issues hub): https://migration.gov.az/en/useful/43",
        ]),
    },
]


CITIES = [
    {
        "city_id": "CITY-ALM",
        "name": "Алматы",
        "country": "Казахстан",
        "median_rent": 850,
        "cost_of_living": 620,
        "commute_guidance": "Для частого офиса целевой коридор до 45 минут, 46-60 минут допустим как компромисс.",
        "popular_districts": _j(["DST-ALM-02", "DST-ALM-05"]),
        "description": "Город с заметным компромиссом между центральностью и площадью жилья.",
    },
    {
        "city_id": "CITY-EVN",
        "name": "Ереван",
        "country": "Армения",
        "median_rent": 1080,
        "cost_of_living": 720,
        "commute_guidance": "Хороший баланс для пары обычно находится в 25-40 минутах до офиса.",
        "popular_districts": _j(["DST-EVN-03", "DST-EVN-05"]),
        "description": "Спрос и центральность быстро повышают стоимость, но качество жизни остаётся сильным.",
    },
    {
        "city_id": "CITY-TAS",
        "name": "Ташкент",
        "country": "Узбекистан",
        "median_rent": 980,
        "cost_of_living": 640,
        "commute_guidance": "Для семейного кейса лучше искать район со стабильной логистикой и школами.",
        "popular_districts": _j(["DST-TAS-02", "DST-TAS-03", "DST-TAS-04"]),
        "description": "Город, где сильные семейные районы могут заметно отличаться по школам и транспорту.",
    },
    {
        "city_id": "CITY-MIN",
        "name": "Минск",
        "country": "Беларусь",
        "median_rent": 860,
        "cost_of_living": 580,
        "commute_guidance": "Для срочного переезда удобнее районы с готовым меблированным фондом и понятной логистикой.",
        "popular_districts": _j(["DST-MIN-01", "DST-MIN-03"]),
        "description": "Рынок относительно стабилен, но чувствителен к документам и формату договора.",
    },
    {
        "city_id": "CITY-BAK",
        "name": "Баку",
        "country": "Азербайджан",
        "median_rent": 1020,
        "cost_of_living": 690,
        "commute_guidance": "Семейный pet-friendly фонд в центре обычно выходит за рамки базового бюджета.",
        "popular_districts": _j(["DST-BAK-01", "DST-BAK-06"]),
        "description": "Центр дорогой, а семейные районы дают лучший бюджетный баланс ценой дополнительного времени в пути.",
    },
]


DISTRICTS = [
    {
        "district_id": "DST-ALM-02",
        "city": "Алматы",
        "country": "Казахстан",
        "name": "Бостандык офисный коридор",
        "avg_rent_from": 750,
        "avg_rent_to": 950,
        "is_central": 1,
        "family_friendly": 0,
        "pet_friendly": 1,
        "safety_score": 0.82,
        "school_score": 0.68,
        "transit_score": 0.88,
        "commute_to_center_minutes": 18,
        "description": "Хороший баланс для сотрудников с частым офисом: ближе к деловым зонам, но без премии самого центра.",
    },
    {
        "district_id": "DST-ALM-05",
        "city": "Алматы",
        "country": "Казахстан",
        "name": "Ауэзов семейная жилая зона",
        "avg_rent_from": 650,
        "avg_rent_to": 800,
        "is_central": 0,
        "family_friendly": 1,
        "pet_friendly": 1,
        "safety_score": 0.76,
        "school_score": 0.72,
        "transit_score": 0.63,
        "commute_to_center_minutes": 33,
        "description": "Более доступная зона с заметно лучшей ценой, но длиннее маршрут до делового коридора.",
    },
    {
        "district_id": "DST-EVN-03",
        "city": "Ереван",
        "country": "Армения",
        "name": "Арабкир гибкий городской район",
        "avg_rent_from": 950,
        "avg_rent_to": 1300,
        "is_central": 1,
        "family_friendly": 1,
        "pet_friendly": 1,
        "safety_score": 0.81,
        "school_score": 0.73,
        "transit_score": 0.84,
        "commute_to_center_minutes": 17,
        "description": "Устойчивый выбор для пары: комфортная среда, есть pet-friendly фонд без премии абсолютного центра.",
    },
    {
        "district_id": "DST-EVN-05",
        "city": "Ереван",
        "country": "Армения",
        "name": "Давташен просторный жилой кластер",
        "avg_rent_from": 980,
        "avg_rent_to": 1250,
        "is_central": 0,
        "family_friendly": 1,
        "pet_friendly": 1,
        "safety_score": 0.79,
        "school_score": 0.78,
        "transit_score": 0.71,
        "commute_to_center_minutes": 27,
        "description": "Чуть дальше от центра, но проще найти более лояльные условия для нескольких животных.",
    },
    {
        "district_id": "DST-TAS-02",
        "city": "Ташкент",
        "country": "Узбекистан",
        "name": "Ташкент City ближний офисный контур",
        "avg_rent_from": 1250,
        "avg_rent_to": 1550,
        "is_central": 1,
        "family_friendly": 0,
        "pet_friendly": 0,
        "safety_score": 0.83,
        "school_score": 0.66,
        "transit_score": 0.9,
        "commute_to_center_minutes": 12,
        "description": "Лучший по времени в пути район, но семейные варианты здесь дороже и компактнее.",
    },
    {
        "district_id": "DST-TAS-03",
        "city": "Ташкент",
        "country": "Узбекистан",
        "name": "Мирабад сбалансированный деловой район",
        "avg_rent_from": 900,
        "avg_rent_to": 1350,
        "is_central": 0,
        "family_friendly": 1,
        "pet_friendly": 0,
        "safety_score": 0.81,
        "school_score": 0.71,
        "transit_score": 0.83,
        "commute_to_center_minutes": 18,
        "description": "Сильный баланс аренды и времени в пути, часто подходит как универсальный компромисс.",
    },
    {
        "district_id": "DST-TAS-04",
        "city": "Ташкент",
        "country": "Узбекистан",
        "name": "Юнусабад семейный район",
        "avg_rent_from": 1000,
        "avg_rent_to": 1400,
        "is_central": 0,
        "family_friendly": 1,
        "pet_friendly": 1,
        "safety_score": 0.84,
        "school_score": 0.88,
        "transit_score": 0.74,
        "commute_to_center_minutes": 28,
        "description": "Один из лучших районов для семейного сценария по школам и ежедневной инфраструктуре.",
    },
    {
        "district_id": "DST-TAS-06",
        "city": "Ташкент",
        "country": "Узбекистан",
        "name": "Сергели доступный компромисс",
        "avg_rent_from": 780,
        "avg_rent_to": 1050,
        "is_central": 0,
        "family_friendly": 1,
        "pet_friendly": 1,
        "safety_score": 0.68,
        "school_score": 0.61,
        "transit_score": 0.58,
        "commute_to_center_minutes": 39,
        "description": "Бюджетный вариант с большим запасом по цене, но уступает по логистике и инфраструктуре.",
    },
    {
        "district_id": "DST-MIN-01",
        "city": "Минск",
        "country": "Беларусь",
        "name": "Центральный временный фонд",
        "avg_rent_from": 850,
        "avg_rent_to": 1100,
        "is_central": 1,
        "family_friendly": 0,
        "pet_friendly": 0,
        "safety_score": 0.79,
        "school_score": 0.67,
        "transit_score": 0.89,
        "commute_to_center_minutes": 10,
        "description": "Лучше всего подходит для временного заселения и короткой логистики в первые недели.",
    },
    {
        "district_id": "DST-MIN-03",
        "city": "Минск",
        "country": "Беларусь",
        "name": "Победителей жилой кластер",
        "avg_rent_from": 820,
        "avg_rent_to": 980,
        "is_central": 0,
        "family_friendly": 1,
        "pet_friendly": 1,
        "safety_score": 0.82,
        "school_score": 0.77,
        "transit_score": 0.76,
        "commute_to_center_minutes": 24,
        "description": "Сильный баланс долгосрочной цены и жилой инфраструктуры после закрытия документных вопросов.",
    },
    {
        "district_id": "DST-BAK-01",
        "city": "Баку",
        "country": "Азербайджан",
        "name": "Центр и деловой контур",
        "avg_rent_from": 1200,
        "avg_rent_to": 1700,
        "is_central": 1,
        "family_friendly": 0,
        "pet_friendly": 0,
        "safety_score": 0.83,
        "school_score": 0.7,
        "transit_score": 0.92,
        "commute_to_center_minutes": 8,
        "description": "Лучший район по времени в пути, но семейный pet-friendly фонд здесь дорогой и ограниченный.",
    },
    {
        "district_id": "DST-BAK-06",
        "city": "Баку",
        "country": "Азербайджан",
        "name": "Ясамал семейный компромисс",
        "avg_rent_from": 820,
        "avg_rent_to": 980,
        "is_central": 0,
        "family_friendly": 1,
        "pet_friendly": 1,
        "safety_score": 0.77,
        "school_score": 0.8,
        "transit_score": 0.69,
        "commute_to_center_minutes": 24,
        "description": "Рабочий семейный компромисс по бюджету, но обычно требует 35-45 минут до офиса.",
    },
]


CLIENTS = [
    {
        "client_id": "CL-001",
        "full_name": "Илья Смирнов",
        "citizenship": "Россия",
        "employment_type": "software_engineer",
        "monthly_income": 2800,
        "income_currency": "USD",
        "has_local_guarantor": 0,
        "has_passport": 1,
        "employer_support": 0,
        "notes": _j(["Работает в офисе 4 дня в неделю."]),
    },
    {
        "client_id": "CL-002",
        "full_name": "Марина и Сергей Громовы",
        "citizenship": "Россия",
        "employment_type": "product_team",
        "monthly_income": 3600,
        "income_currency": "USD",
        "has_local_guarantor": 0,
        "has_passport": 1,
        "employer_support": 0,
        "notes": _j(["Переезд парой с кошкой."]),
    },
    {
        "client_id": "CL-003",
        "full_name": "Семья Ахмедовых",
        "citizenship": "Россия",
        "employment_type": "operations_manager",
        "monthly_income": 4300,
        "income_currency": "USD",
        "has_local_guarantor": 0,
        "has_passport": 1,
        "employer_support": 0,
        "notes": _j(["Семья с ребёнком школьного возраста."]),
    },
    {
        "client_id": "CL-004",
        "full_name": "Алексей Котов",
        "citizenship": "Россия",
        "employment_type": "analyst",
        "monthly_income": 3000,
        "income_currency": "USD",
        "has_local_guarantor": 0,
        "has_passport": 1,
        "employer_support": 0,
        "notes": _j(["Документы для долгосрочной аренды ещё не готовы."]),
    },
    {
        "client_id": "CL-005",
        "full_name": "Семья Вагаповых",
        "citizenship": "Россия",
        "employment_type": "finance",
        "monthly_income": 3200,
        "income_currency": "USD",
        "has_local_guarantor": 0,
        "has_passport": 1,
        "employer_support": 0,
        "notes": _j(["Семья с ребёнком и собакой."]),
    },
    {
        "client_id": "CL-006",
        "full_name": "Руслан Каримов",
        "citizenship": "Россия",
        "employment_type": "sales",
        "monthly_income": 4500,
        "income_currency": "USD",
        "has_local_guarantor": 0,
        "has_passport": 0,
        "employer_support": 0,
        "notes": _j(["На старте только внутренний паспорт."]),
    },
]


CLIENT_PREFERENCES = [
    {
        "client_id": "CL-001",
        "preferred_districts": _j(["DST-ALM-02", "DST-ALM-05"]),
        "furnished": 1,
        "elevator": None,
        "floor_max": None,
        "max_commute_minutes": 45,
        "school_requirement": 0,
        "rooms_min": 1,
        "lease_months": 12,
        "comments": "Нужна мебель и без слишком долгой дороги.",
    },
    {
        "client_id": "CL-002",
        "preferred_districts": _j(["DST-EVN-03", "DST-EVN-05"]),
        "furnished": 1,
        "elevator": None,
        "floor_max": None,
        "max_commute_minutes": 40,
        "school_requirement": 0,
        "rooms_min": 1,
        "lease_months": 12,
        "comments": "Главное, чтобы пускали с животным.",
    },
    {
        "client_id": "CL-003",
        "preferred_districts": _j(["DST-TAS-04", "DST-TAS-06"]),
        "furnished": 1,
        "elevator": 1,
        "floor_max": 8,
        "max_commute_minutes": 45,
        "school_requirement": 1,
        "rooms_min": 2,
        "lease_months": 12,
        "comments": "Нужны школа, спокойный район и бытовая инфраструктура.",
    },
    {
        "client_id": "CL-004",
        "preferred_districts": _j(["DST-MIN-01", "DST-MIN-03"]),
        "furnished": 1,
        "elevator": None,
        "floor_max": None,
        "max_commute_minutes": 35,
        "school_requirement": 0,
        "rooms_min": 1,
        "lease_months": 12,
        "comments": "Срочный переезд, документы догружаются.",
    },
    {
        "client_id": "CL-005",
        "preferred_districts": _j(["DST-BAK-01"]),
        "furnished": 1,
        "elevator": 1,
        "floor_max": 10,
        "max_commute_minutes": 20,
        "school_requirement": 1,
        "rooms_min": 2,
        "lease_months": 12,
        "comments": "Собака, семья, нужен центр и короткая дорога.",
    },
    {
        "client_id": "CL-006",
        "preferred_districts": _j(["DST-TAS-03"]),
        "furnished": 1,
        "elevator": None,
        "floor_max": None,
        "max_commute_minutes": 40,
        "school_requirement": 0,
        "rooms_min": 1,
        "lease_months": 12,
        "comments": "Пока не закрыт вопрос по документам.",
    },
]


CASES = [
    {
        "case_id": "R-0001",
        "client_id": "CL-001",
        "city": "Алматы",
        "country": "Казахстан",
        "move_in_date": "2026-07-05",
        "office_zone": "Esentai Business Corridor",
        "monthly_budget": 900,
        "upfront_budget": 2000,
        "max_commute_minutes": 45,
        "preferred_districts": _j(["DST-ALM-02", "DST-ALM-05"]),
        "furnished": 1,
        "rooms_min": 1,
        "lease_months": 12,
        "urgency_level": "normal",
        "document_status": "complete",
        "needs_school_access": 0,
        "notes": _j(["Гибридный график, офис почти каждый день."]),
    },
    {
        "case_id": "R-0002",
        "client_id": "CL-002",
        "city": "Ереван",
        "country": "Армения",
        "move_in_date": "2026-07-10",
        "office_zone": "Northern Avenue",
        "monthly_budget": 1200,
        "upfront_budget": 2600,
        "max_commute_minutes": 40,
        "preferred_districts": _j(["DST-EVN-03", "DST-EVN-05"]),
        "furnished": 1,
        "rooms_min": 1,
        "lease_months": 12,
        "urgency_level": "normal",
        "document_status": "complete",
        "needs_school_access": 0,
        "notes": _j(["Пара с кошкой."]),
    },
    {
        "case_id": "R-0003",
        "client_id": "CL-003",
        "city": "Ташкент",
        "country": "Узбекистан",
        "move_in_date": "2026-07-15",
        "office_zone": "Tashkent City",
        "monthly_budget": 1300,
        "upfront_budget": 3000,
        "max_commute_minutes": 45,
        "preferred_districts": _j(["DST-TAS-04", "DST-TAS-06"]),
        "furnished": 1,
        "rooms_min": 2,
        "lease_months": 12,
        "urgency_level": "normal",
        "document_status": "complete",
        "needs_school_access": 1,
        "notes": _j(["Семья с ребёнком, офис посещается в гибридном режиме."]),
    },
    {
        "case_id": "R-0004",
        "client_id": "CL-004",
        "city": "Минск",
        "country": "Беларусь",
        "move_in_date": "2026-06-23",
        "office_zone": "Victory Avenue",
        "monthly_budget": 1000,
        "upfront_budget": 900,
        "max_commute_minutes": 35,
        "preferred_districts": _j(["DST-MIN-01", "DST-MIN-03"]),
        "furnished": 1,
        "rooms_min": 1,
        "lease_months": 12,
        "urgency_level": "urgent",
        "document_status": "incomplete_docs",
        "needs_school_access": 0,
        "notes": _j(["Заезд менее чем через 10 дней, локальные документы не готовы."]),
    },
    {
        "case_id": "R-0005",
        "client_id": "CL-005",
        "city": "Баку",
        "country": "Азербайджан",
        "move_in_date": "2026-07-12",
        "office_zone": "White City",
        "monthly_budget": 950,
        "upfront_budget": 2300,
        "max_commute_minutes": 20,
        "preferred_districts": _j(["DST-BAK-01"]),
        "furnished": 1,
        "rooms_min": 2,
        "lease_months": 12,
        "urgency_level": "normal",
        "document_status": "complete",
        "needs_school_access": 1,
        "notes": _j(["Семья с собакой, нужен центр и короткая дорога до офиса."]),
    },
    {
        "case_id": "R-0006",
        "client_id": "CL-006",
        "city": "Ташкент",
        "country": "Узбекистан",
        "move_in_date": "2026-07-08",
        "office_zone": "Mirobod Office Cluster",
        "monthly_budget": 1400,
        "upfront_budget": 3000,
        "max_commute_minutes": 40,
        "preferred_districts": _j(["DST-TAS-03"]),
        "furnished": 1,
        "rooms_min": 1,
        "lease_months": 12,
        "urgency_level": "normal",
        "document_status": "internal_passport_only",
        "needs_school_access": 0,
        "notes": _j(["Подбор по жилью реалистичен, но документный статус не закрыт."]),
    },
]


HOUSEHOLD_MEMBERS = [
    ("HM-001", "R-0001", "CL-001", "self", "adult", None, 0, ""),
    ("HM-002", "R-0002", "CL-002", "adult_1", "adult", None, 0, ""),
    ("HM-003", "R-0002", "CL-002", "adult_2", "adult", None, 0, ""),
    ("HM-004", "R-0002", "CL-002", "pet", None, "cat", 0, "Одна кошка"),
    ("HM-005", "R-0003", "CL-003", "adult_1", "adult", None, 0, ""),
    ("HM-006", "R-0003", "CL-003", "adult_2", "adult", None, 0, ""),
    ("HM-007", "R-0003", "CL-003", "child", "child", None, 1, "Школьный возраст"),
    ("HM-008", "R-0004", "CL-004", "self", "adult", None, 0, ""),
    ("HM-009", "R-0005", "CL-005", "adult_1", "adult", None, 0, ""),
    ("HM-010", "R-0005", "CL-005", "adult_2", "adult", None, 0, ""),
    ("HM-011", "R-0005", "CL-005", "child", "child", None, 1, "Нужна школа рядом"),
    ("HM-012", "R-0005", "CL-005", "pet", None, "dog", 0, "Собака среднего размера"),
    ("HM-013", "R-0006", "CL-006", "self", "adult", None, 0, ""),
]


SERVICES = [
    {
        "service_id": "SV-TEMP-001",
        "city": "Минск",
        "country": "Беларусь",
        "service_type": "temporary_housing",
        "name": "Стартовое временное жильё на 2-3 недели",
        "cost": 700,
        "currency": "USD",
        "description": "Краткосрочное меблированное проживание до закрытия документных вопросов по стандартной аренде.",
        "suitable_for": _j(["urgent_move", "incomplete_docs"]),
    },
    {
        "service_id": "SV-LEGAL-002",
        "city": "Ташкент",
        "country": "Узбекистан",
        "service_type": "legal_support",
        "name": "Проверка документного маршрута и договора",
        "cost": 450,
        "currency": "USD",
        "description": "Помощь с проверкой въездных документов, регистрации и рисков подписания договора.",
        "suitable_for": _j(["passport_issue", "escalation"]),
    },
    {
        "service_id": "SV-BROKER-003",
        "city": "Алматы",
        "country": "Казахстан",
        "service_type": "broker_support",
        "name": "Локальный брокер для офисных районов",
        "cost": 200,
        "currency": "USD",
        "description": "Подбор и переговоры по объектам рядом с деловым коридором.",
        "suitable_for": _j(["office_commute", "single_professional"]),
    },
    {
        "service_id": "SV-PET-004",
        "city": "Ереван",
        "country": "Армения",
        "service_type": "pet_relocation",
        "name": "Пакет для релокации с животными",
        "cost": 180,
        "currency": "USD",
        "description": "Подготовка pet-friendly shortlists и помощь с подтверждением условий по депозиту.",
        "suitable_for": _j(["pet_owner"]),
    },
    {
        "service_id": "SV-SCHOOL-005",
        "city": "Ташкент",
        "country": "Узбекистан",
        "service_type": "school_consulting",
        "name": "Сопровождение по школам и семейным районам",
        "cost": 220,
        "currency": "USD",
        "description": "Помогает сузить семейные районы по школам, безопасности и маршрутам.",
        "suitable_for": _j(["family", "school_required"]),
    },
    {
        "service_id": "SV-LEASE-006",
        "city": "Баку",
        "country": "Азербайджан",
        "service_type": "lease_review",
        "name": "Проверка условий повышенного депозита",
        "cost": 150,
        "currency": "USD",
        "description": "Помогает оценить договор и переговоры по повышенному депозиту.",
        "suitable_for": _j(["high_deposit"]),
    },
    {
        "service_id": "SV-MOVE-007",
        "city": None,
        "country": None,
        "service_type": "moving_support",
        "name": "Базовая логистика переезда",
        "cost": 300,
        "currency": "USD",
        "description": "Организация перевозки вещей и базового заселения.",
        "suitable_for": _j(["general"]),
    },
]


LISTINGS = [
    ("LS-ALM-014", "Алматы", "Казахстан", "DST-ALM-02", "Бостандык офисный коридор", "Меблированная 1-bedroom рядом с офисным коридором", "apartment", 820, "USD", 1.0, 230, 80, 60, 46, 1, "2026-06-28", 1, 0, None, 1, 1, 7, 2, 38, 18, 12, 0, 3.0, 0, _j(["Хорошая транспортная доступность", "Полностью меблирована"]), _j([])),
    ("LS-ALM-018", "Алматы", "Казахстан", "DST-ALM-02", "Бостандык офисный коридор", "Компактная студия в деловом кластере", "studio", 760, "USD", 1.0, 180, 50, 55, 31, 1, "2026-06-24", 1, 0, None, 1, 1, 5, 1, 28, 15, 12, 0, 3.0, 0, _j(["Очень близко к офису"]), _j(["compact_layout"])),
    ("LS-ALM-022", "Алматы", "Казахстан", "DST-ALM-02", "Бостандык офисный коридор", "1-bedroom с ремонтом и чуть большей площадью", "apartment", 860, "USD", 1.0, 240, 110, 70, 50, 1, "2026-06-30", 1, 0, None, 1, 1, 9, 2, 44, 18, 12, 0, 3.2, 1, _j(["Ремонт выше рынка"]), _j(["income_check"])),
    ("LS-ALM-024", "Алматы", "Казахстан", "DST-ALM-05", "Ауэзов семейная жилая зона", "Доступная квартира без мебели", "apartment", 690, "USD", 1.0, 120, 30, 50, 44, 1, "2026-06-26", 0, 1, 1, 1, 0, 4, 2, 55, 32, 12, 0, 2.8, 0, _j(["Цена заметно ниже рынка"]), _j(["no_furniture"])),
    ("LS-ALM-029", "Алматы", "Казахстан", "DST-ALM-05", "Ауэзов семейная жилая зона", "Сбалансированная 1-bedroom в более доступном районе", "apartment", 740, "USD", 1.0, 130, 40, 55, 45, 1, "2026-06-29", 1, 1, 1, 1, 1, 6, 2, 54, 31, 12, 0, 2.7, 0, _j(["Лучше попадает в сниженный бюджет"]), _j([])),
    ("LS-ALM-032", "Алматы", "Казахстан", "DST-ALM-05", "Ауэзов семейная жилая зона", "Большая 2-bedroom с повышенным депозитом", "apartment", 920, "USD", 2.0, 150, 0, 80, 67, 2, "2026-07-02", 1, 1, 2, 1, 1, 10, 4, 57, 35, 12, 0, 3.0, 1, _j(["Хорошая площадь"]), _j(["high_deposit"])),
    ("LS-EVN-031", "Ереван", "Армения", "DST-EVN-03", "Арабкир гибкий городской район", "1-bedroom для пары с одним питомцем", "apartment", 1050, "USD", 1.0, 250, 200, 65, 52, 1, "2026-07-01", 1, 1, 1, 1, 1, 5, 2, 30, 17, 12, 0, 3.0, 0, _j(["Разрешена одна кошка", "Гибкое окно заселения"]), _j([])),
    ("LS-EVN-034", "Ереван", "Армения", "DST-EVN-03", "Арабкир гибкий городской район", "Центральная студия без pet-friendly статуса", "studio", 890, "USD", 1.0, 180, 60, 55, 34, 1, "2026-06-25", 1, 0, None, 0, 1, 8, 1, 24, 14, 12, 0, 3.0, 0, _j(["Дешевле основного варианта"]), _j(["no_pets"])),
    ("LS-EVN-037", "Ереван", "Армения", "DST-EVN-05", "Давташен просторный жилой кластер", "2-bedroom для пары и домашнего офиса", "apartment", 1260, "USD", 1.0, 220, 80, 70, 64, 2, "2026-07-05", 1, 1, 2, 1, 1, 6, 3, 37, 26, 12, 0, 3.1, 0, _j(["Больше пространства"]), _j(["over_budget_soft"])),
    ("LS-EVN-041", "Ереван", "Армения", "DST-EVN-03", "Арабкир гибкий городской район", "Тихая 1-bedroom ближе к центру", "apartment", 1090, "USD", 1.0, 260, 120, 60, 49, 1, "2026-06-29", 1, 1, 1, 1, 1, 4, 2, 27, 15, 12, 0, 3.2, 1, _j(["Сильная локация"]), _j(["income_check"])),
    ("LS-EVN-044", "Ереван", "Армения", "DST-EVN-05", "Давташен просторный жилой кластер", "Pet-friendly 2-bedroom для пары с двумя кошками", "apartment", 1120, "USD", 1.5, 220, 80, 70, 58, 2, "2026-07-03", 1, 1, 2, 1, 1, 5, 3, 37, 25, 12, 0, 3.0, 0, _j(["Лояльный объект для двух животных"]), _j(["pet_deposit"])),
    ("LS-EVN-047", "Ереван", "Армения", "DST-EVN-05", "Давташен просторный жилой кластер", "Доступная квартира с поздним заселением", "apartment", 980, "USD", 1.0, 150, 50, 55, 48, 1, "2026-07-20", 1, 1, 1, 1, 0, 9, 2, 40, 28, 12, 0, 2.8, 0, _j(["Дешевле основного варианта"]), _j(["late_availability"])),
    ("LS-TAS-018", "Ташкент", "Узбекистан", "DST-TAS-04", "Юнусабад семейный район", "Семейная 2-bedroom у школы и магазинов", "apartment", 1180, "USD", 1.0, 300, 290, 80, 72, 2, "2026-07-05", 1, 1, 1, 1, 1, 7, 4, 42, 28, 12, 0, 3.0, 0, _j(["Сильная школьная инфраструктура", "Спокойный район"]), _j([])),
    ("LS-TAS-021", "Ташкент", "Узбекистан", "DST-TAS-02", "Ташкент City ближний офисный контур", "Близкая к офису 1-bedroom", "apartment", 1450, "USD", 1.0, 260, 100, 85, 44, 1, "2026-07-01", 1, 0, None, 0, 1, 11, 2, 24, 11, 12, 0, 3.3, 1, _j(["Лучшее время в пути"]), _j(["small_for_family", "over_budget"])),
    ("LS-TAS-024", "Ташкент", "Узбекистан", "DST-TAS-06", "Сергели доступный компромисс", "Бюджетная 2-bedroom на дальней логистике", "apartment", 980, "USD", 1.0, 180, 120, 75, 69, 2, "2026-07-02", 1, 1, 1, 1, 0, 5, 4, 58, 39, 12, 0, 2.7, 0, _j(["Сильная цена"]), _j(["long_commute"])),
    ("LS-TAS-026", "Ташкент", "Узбекистан", "DST-TAS-03", "Мирабад сбалансированный деловой район", "Сбалансированная 1-bedroom в Мирабаде", "apartment", 1210, "USD", 1.0, 250, 130, 70, 50, 1, "2026-07-04", 1, 0, None, 1, 1, 6, 2, 35, 18, 12, 0, 3.0, 1, _j(["Подходит по цене и commute"]), _j(["document_check"])),
    ("LS-TAS-028", "Ташкент", "Узбекистан", "DST-TAS-02", "Ташкент City ближний офисный контур", "Семейная 2-bedroom ближе к офису", "apartment", 1520, "USD", 1.0, 280, 120, 90, 63, 2, "2026-07-08", 1, 0, None, 1, 1, 9, 4, 29, 12, 12, 0, 3.5, 1, _j(["Вписывается в commute до 30 минут"]), _j(["over_budget", "strict_docs"])),
    ("LS-TAS-033", "Ташкент", "Узбекистан", "DST-TAS-04", "Юнусабад семейный район", "3-bedroom с повышенным депозитом", "apartment", 1290, "USD", 2.0, 240, 100, 85, 83, 3, "2026-07-06", 1, 1, 1, 1, 1, 12, 5, 44, 29, 12, 0, 3.1, 1, _j(["Отличная площадь"]), _j(["high_deposit"])),
    ("LS-TAS-036", "Ташкент", "Узбекистан", "DST-TAS-06", "Сергели доступный компромисс", "Доступная 1-bedroom для одного арендатора", "apartment", 820, "USD", 1.0, 120, 50, 60, 41, 1, "2026-06-27", 1, 1, 1, 1, 0, 3, 2, 61, 40, 12, 0, 2.5, 0, _j(["Сильный бюджетный запас"]), _j(["too_far_for_daily_office"])),
    ("LS-MIN-TMP-003", "Минск", "Беларусь", "DST-MIN-01", "Центральный временный фонд", "Краткосрочные апартаменты на 2-3 недели", "temporary_housing", 980, "USD", 0.0, 0, 700, 0, 36, 1, "2026-06-20", 1, 0, None, 0, 1, 3, 2, 25, 10, 1, 1, None, 0, _j(["Оплата по модели booking only upfront"]), _j(["booking_only_upfront"])),
    ("LS-MIN-011", "Минск", "Беларусь", "DST-MIN-01", "Центральный временный фонд", "Долгосрочная квартира с жёсткой проверкой документов", "apartment", 880, "USD", 1.0, 170, 50, 65, 42, 1, "2026-06-22", 1, 0, None, 1, 1, 5, 2, 22, 11, 12, 0, 3.0, 1, _j(["Подходит по цене"]), _j(["full_docs_required"])),
    ("LS-MIN-017", "Минск", "Беларусь", "DST-MIN-03", "Победителей жилой кластер", "Долгосрочная 1-bedroom после закрытия документов", "apartment", 910, "USD", 1.0, 180, 100, 70, 47, 1, "2026-07-14", 1, 1, 1, 1, 1, 6, 2, 27, 23, 12, 0, 2.9, 0, _j(["Хороший долгосрочный баланс"]), _j([])),
    ("LS-MIN-021", "Минск", "Беларусь", "DST-MIN-03", "Победителей жилой кластер", "2-bedroom с высоким депозитом", "apartment", 970, "USD", 2.0, 140, 80, 75, 63, 2, "2026-07-05", 1, 1, 1, 1, 1, 10, 3, 30, 24, 12, 0, 3.0, 1, _j(["Неплохая семейная площадь"]), _j(["high_deposit", "income_check"])),
    ("LS-MIN-025", "Минск", "Беларусь", "DST-MIN-03", "Победителей жилой кластер", "Доступная квартира без мебели", "apartment", 760, "USD", 1.0, 100, 40, 60, 40, 1, "2026-06-26", 0, 1, 1, 1, 0, 2, 2, 35, 25, 12, 0, 2.5, 0, _j(["Дёшево для района"]), _j(["no_furniture"])),
    ("LS-MIN-029", "Минск", "Беларусь", "DST-MIN-01", "Центральный временный фонд", "Сервисные апартаменты на месяц", "temporary_housing", 1040, "USD", 0.5, 0, 300, 0, 34, 1, "2026-06-19", 1, 0, None, 0, 1, 4, 2, 18, 9, 1, 1, None, 0, _j(["Удобно на короткий срок"]), _j([])),
    ("LS-BAK-018", "Баку", "Азербайджан", "DST-BAK-01", "Центр и деловой контур", "Центральная 2-bedroom без pet-friendly статуса", "apartment", 1280, "USD", 1.0, 240, 100, 90, 61, 2, "2026-07-03", 1, 0, None, 1, 1, 8, 4, 16, 8, 12, 0, 3.2, 1, _j(["Отличный commute"]), _j(["no_pets", "over_budget"])),
    ("LS-BAK-022", "Баку", "Азербайджан", "DST-BAK-01", "Центр и деловой контур", "1-bedroom в центре для пары", "apartment", 1100, "USD", 1.0, 180, 90, 80, 43, 1, "2026-07-01", 1, 0, None, 0, 1, 12, 2, 14, 7, 12, 0, 3.1, 1, _j(["Лучший по логистике"]), _j(["small_for_family", "over_budget"])),
    ("LS-BAK-024", "Баку", "Азербайджан", "DST-BAK-06", "Ясамал семейный компромисс", "Семейная 2-bedroom с поздним стартом", "apartment", 860, "USD", 1.0, 170, 100, 75, 66, 2, "2026-07-22", 1, 1, 1, 1, 1, 7, 4, 47, 25, 12, 0, 2.8, 0, _j(["Хорошая цена"]), _j(["late_availability"])),
    ("LS-BAK-027", "Баку", "Азербайджан", "DST-BAK-06", "Ясамал семейный компромисс", "Pet-friendly 2-bedroom для семьи", "apartment", 890, "USD", 1.0, 220, 200, 75, 68, 2, "2026-07-06", 1, 1, 1, 1, 1, 5, 4, 40, 24, 12, 0, 2.9, 0, _j(["Укладывается в бюджет при commute до 45 минут"]), _j([])),
    ("LS-BAK-031", "Баку", "Азербайджан", "DST-BAK-06", "Ясамал семейный компромисс", "3-bedroom с повышенным депозитом", "apartment", 960, "USD", 2.0, 180, 70, 85, 82, 3, "2026-07-05", 1, 1, 2, 1, 1, 9, 5, 42, 26, 12, 0, 3.0, 1, _j(["Хорошая площадь"]), _j(["high_deposit", "slightly_over_budget"])),
    ("LS-BAK-035", "Баку", "Азербайджан", "DST-BAK-01", "Центр и деловой контур", "Премиальный центр с гибким договором", "apartment", 1490, "USD", 1.0, 260, 130, 100, 73, 2, "2026-07-02", 1, 1, 1, 1, 1, 10, 4, 18, 8, 6, 1, 3.5, 1, _j(["Очень гибкий договор"]), _j(["premium_price"])),
]


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def seed_database(db_path: Path = DEFAULT_DB_PATH) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = _connect(db_path)
    with connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        connection.executemany(
            """
            INSERT INTO countries (
                country_id, name, relocation_by_internal_passport, residence_orientation,
                citizenship_orientation, cost_of_living_single_range,
                cost_of_living_family_range, primary_city, notes
            ) VALUES (
                :country_id, :name, :relocation_by_internal_passport, :residence_orientation,
                :citizenship_orientation, :cost_of_living_single_range,
                :cost_of_living_family_range, :primary_city, :notes
            )
            """,
            COUNTRIES,
        )

        connection.executemany(
            """
            INSERT INTO cities (
                city_id, name, country, median_rent, cost_of_living, commute_guidance,
                popular_districts, description
            ) VALUES (
                :city_id, :name, :country, :median_rent, :cost_of_living, :commute_guidance,
                :popular_districts, :description
            )
            """,
            CITIES,
        )

        connection.executemany(
            """
            INSERT INTO districts (
                district_id, city, country, name, avg_rent_from, avg_rent_to,
                is_central, family_friendly, pet_friendly, safety_score, school_score,
                transit_score, commute_to_center_minutes, description
            ) VALUES (
                :district_id, :city, :country, :name, :avg_rent_from, :avg_rent_to,
                :is_central, :family_friendly, :pet_friendly, :safety_score, :school_score,
                :transit_score, :commute_to_center_minutes, :description
            )
            """,
            DISTRICTS,
        )

        connection.executemany(
            """
            INSERT INTO clients (
                client_id, full_name, citizenship, employment_type, monthly_income,
                income_currency, has_local_guarantor, has_passport, employer_support, notes
            ) VALUES (
                :client_id, :full_name, :citizenship, :employment_type, :monthly_income,
                :income_currency, :has_local_guarantor, :has_passport, :employer_support, :notes
            )
            """,
            CLIENTS,
        )

        connection.executemany(
            """
            INSERT INTO client_preferences (
                client_id, preferred_districts, furnished, elevator, floor_max,
                max_commute_minutes, school_requirement, rooms_min, lease_months, comments
            ) VALUES (
                :client_id, :preferred_districts, :furnished, :elevator, :floor_max,
                :max_commute_minutes, :school_requirement, :rooms_min, :lease_months, :comments
            )
            """,
            CLIENT_PREFERENCES,
        )

        connection.executemany(
            """
            INSERT INTO relocation_cases (
                case_id, client_id, city, country, move_in_date, office_zone, monthly_budget,
                upfront_budget, max_commute_minutes, preferred_districts, furnished, rooms_min,
                lease_months, urgency_level, document_status, needs_school_access, notes
            ) VALUES (
                :case_id, :client_id, :city, :country, :move_in_date, :office_zone, :monthly_budget,
                :upfront_budget, :max_commute_minutes, :preferred_districts, :furnished, :rooms_min,
                :lease_months, :urgency_level, :document_status, :needs_school_access, :notes
            )
            """,
            CASES,
        )

        connection.executemany(
            """
            INSERT INTO household_members (
                member_id, case_id, client_id, relation, age_group, pet_type,
                requires_school, special_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            HOUSEHOLD_MEMBERS,
        )

        connection.executemany(
            """
            INSERT INTO listings (
                listing_id, city, country, district_id, district_name, title, property_type,
                monthly_rent, currency, deposit_months, agency_fee, move_in_fee, utilities_monthly,
                area_sqm, rooms, available_from, furnished, pet_friendly, max_pets,
                children_friendly, elevator, floor, max_occupants, commute_to_office_minutes,
                commute_to_center_minutes, min_lease_months, short_term_available,
                required_income_multiplier, income_verification_required, notes, landlord_flags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            LISTINGS,
        )

        connection.executemany(
            """
            INSERT INTO relocation_services (
                service_id, city, country, service_type, name, cost, currency,
                description, suitable_for
            ) VALUES (
                :service_id, :city, :country, :service_type, :name, :cost, :currency,
                :description, :suitable_for
            )
            """,
            SERVICES,
        )
    connection.close()
    return db_path


if __name__ == "__main__":
    seeded = seed_database()
    print(f"Seeded relocation database at {seeded}")
