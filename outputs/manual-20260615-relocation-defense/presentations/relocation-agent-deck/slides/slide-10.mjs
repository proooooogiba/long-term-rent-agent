import { fixed, fr, grow, text } from "@oai/artifact-tool";
import { page, header, row, column, card, chip, styles, bulletLine, statCard } from "./common.mjs";

export async function addSlide(presentation) {
  const slide = presentation.slides.add();

  const pillars = row(
    [fr(1), fr(1), fr(1), fr(1)],
    [
      card([chip("1", "blue"), text("Агентность", { style: styles.cardTitle }), text("роли, память, replanning, verifier", { style: styles.cardBody })], { rows: [fixed(28), fixed(26), fr(1)] }),
      card([chip("2", "teal"), text("Воспроизводимость", { style: styles.cardTitle }), text("demo_stub, локальная БД, QA runner, trace", { style: styles.cardBody })], { rows: [fixed(28), fixed(26), fr(1)] }),
      card([chip("3", "amber"), text("Safety boundary", { style: styles.cardTitle }), text("clarification и escalation вместо ложной уверенности", { style: styles.cardBody })], { rows: [fixed(28), fixed(26), fr(1)] }),
      card([chip("4", "red"), text("Расширяемость", { style: styles.cardTitle }), text("typed tools и config-driven путь для MCP", { style: styles.cardBody })], { rows: [fixed(28), fixed(26), fr(1)] }),
    ],
    14,
  );

  const close = row(
    [fixed(360), fr(1)],
    [
      statCard("Возможные улучшения", "SSO, observability, стабильный live MCP", "blue"),
      card(
        [
          text("Главный тезис для защиты", { style: styles.cardTitle }),
          text("Проект уже показывает базовые признаки агента: он понимает намерение, хранит контекст, вызывает инструменты, может пересобрать решение и умеет остановиться, когда автоматизация небезопасна.", {
            style: styles.body,
            width: grow(1),
          }),
          bulletLine("Главная ценность здесь - в управляемом workflow, а не в одном сильном prompt."),
        ],
        { rows: [fixed(24), fixed(88), fixed(24)] },
      ),
    ],
    18,
  );

  slide.compose(
    page(
      {
        header: header("Что важно вынести", "Финальный слайд закрывает логику всей колоды: от user value до production contour и честных ограничений.", "Conclusion"),
        body: column([fixed(178), fr(1)], [pillars, close], 18),
      },
      "Этот слайд удобно использовать как переход к живому demo или Q and A.",
    ),
  );

  return slide;
}
