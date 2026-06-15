import { fixed, fr, grow, text } from "@oai/artifact-tool";
import { page, header, row, card, chip, styles } from "./common.mjs";

function issueCard(tag, title, symptom, cause, fix, tone) {
  return card(
    [
      chip(tag, tone),
      text(title, { style: styles.cardTitle }),
      text(`symptom: ${symptom}`, { style: styles.cardBody, width: grow(1) }),
      text(`cause: ${cause}`, { style: styles.cardBody, width: grow(1) }),
      text(`fix: ${fix}`, { style: styles.cardBody, width: grow(1) }),
    ],
    { rows: [fixed(28), fixed(40), fixed(34), fixed(44), fixed(44)] },
  );
}

export async function addSlide(presentation) {
  const slide = presentation.slides.add();

  slide.compose(
    page(
      {
        header: header("Проблемы, с которыми мы сталкивались", "Важно показать не только happy path, но и где интеграция реально ломалась.", "Known issues"),
        body: row(
          [fr(1), fr(1)],
          [
            issueCard(
              "routing",
              "LLM routing failed: Connection error",
              "UI падал с traceback вместо ответа.",
              "Live OpenRouter-вызов отваливался по сети, а ранний код не имел мягкого fallback.",
              "Добавлен fallback на demo LLM для routing, intake, replanning и final composition.",
              "red",
            ),
            issueCard(
              "parser",
              "Бюджет брался из даты",
              "Строка 07.07.2026, 1000 usd могла давать budget = 2026.",
              "Fallback-parser ловил первое похожее число и не исключал дату.",
              "Теперь бюджет ищется как сумма с валютой, а дата фильтруется отдельно.",
              "amber",
            ),
            issueCard(
              "currency",
              "Москва + 2000 USD давали пустой Cian",
              "Живой provider отвечал пусто даже при доступном MCP.",
              "USD-бюджет уходил в Cian как RUB, потому что не было currency conversion.",
              "Добавлены budget_currency и конвертация request/result contract.",
              "blue",
            ),
            issueCard(
              "env",
              "Cian ломался только внутри приложения",
              "Изолированный search работал, а полный graph ловил ConnectError.",
              "GraphDependencies подхватывал домашний .env с битым proxy вместо проектного.",
              "Чтение .env ограничено локальным проектом.",
              "teal",
            ),
          ],
          18,
        ),
      },
      "Все кейсы на этом слайде взяты из docs/known_issues_root_causes.md и сжаты до symptom -> cause -> fix.",
    ),
  );

  return slide;
}
