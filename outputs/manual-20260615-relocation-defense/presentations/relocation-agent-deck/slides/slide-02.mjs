import { fixed, fr, grow, text } from "@oai/artifact-tool";
import { page, header, row, column, card, chip, styles, bulletLine, statCard } from "./common.mjs";

export async function addSlide(presentation) {
  const slide = presentation.slides.add();

  const capabilityGrid = row(
    [fr(1), fr(1)],
    [
      card(
        [
          chip("search", "blue"),
          text("Подбор по кейсу", { style: styles.cardTitle }),
          text("Город, бюджет, дата въезда, состав домохозяйства, питомцы и время в пути.", { style: styles.cardBody, width: grow(1) }),
        ],
        { rows: [fixed(28), fixed(24), fr(1)] },
      ),
      card(
        [
          chip("explain", "teal"),
          text("Объяснение выбора", { style: styles.cardTitle }),
          text("Показываем, почему вариант подходит, где компромиссы и какие стартовые расходы.", { style: styles.cardBody, width: grow(1) }),
        ],
        { rows: [fixed(28), fixed(24), fr(1)] },
      ),
      card(
        [
          chip("replan", "amber"),
          text("Пересборка shortlist", { style: styles.cardTitle }),
          text("При изменении бюджета, даты или города агент считает delta и обновляет решение.", { style: styles.cardBody, width: grow(1) }),
        ],
        { rows: [fixed(28), fixed(24), fr(1)] },
      ),
      card(
        [
          chip("escalate", "red"),
          text("Безопасная остановка", { style: styles.cardTitle }),
          text("Документные и квази-юридические кейсы идут в clarification или handoff.", { style: styles.cardBody, width: grow(1) }),
        ],
        { rows: [fixed(28), fixed(24), fr(1)] },
      ),
    ],
    16,
  );

  const flow = card(
    [
      text("Один запуск = один понятный результат", { style: styles.cardTitle }),
      bulletLine("вход: сообщение пользователя + профиль кейса"),
      bulletLine("процесс: search -> score -> verify"),
      bulletLine("выход: shortlist + объяснение + предупреждения"),
      bulletLine("follow-up: пересчёт относительно прошлого run"),
      row(
        [fr(1), fr(1)],
        [
          statCard("top-3", "варианта на экране", "blue"),
          statCard("safe", "guardrails в пайплайне", "teal"),
        ],
        12,
      ),
    ],
    {
      rows: [fixed(24), fixed(22), fixed(22), fixed(22), fixed(22), fixed(110)],
      height: grow(1),
    },
  );

  slide.compose(
    page(
      {
        header: header("Что пользователь получает за один run", "Ценность здесь не в красивом тексте, а в usable shortlist с объяснением и возможностью пересчёта.", "Продукт"),
        body: column(
          [fixed(28), fr(1)],
          [
            chip("Если бюджет меняется после первого ответа, система не начинает всё заново", "amber"),
            row([fr(1.2), fixed(340)], [capabilityGrid, flow], 20),
          ],
          18,
        ),
      },
      "Функции взяты из README и demo-сценариев: search, explain, replan и safe handoff.",
    ),
  );

  return slide;
}
