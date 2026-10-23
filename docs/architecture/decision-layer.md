# Decision Layer

A Decision Layer strukturált döntéseket szolgáltat, alkalmazásszintű műveleteket nem hajt végre. Nem generál természetes nyelvű választ, nem indít toolt, és nem tartalmaz RAG routingot, rangsorolást vagy végrehajtási küszöbértéket.

Az application réteg a `DecisionPort.evaluate(DecisionRequest) -> DecisionResult` aszinkron portot használja. A domain és application réteg nem importál TypeSafe SDK-t. A kivételek a `DecisionError` hierarchia típusai, biztonságos kóddal és retryable jelzővel. A provider konfiguráció alapján választ mock/live/disabled adaptert, hiba esetén nincs automatikus live → mock váltás.

## Szerződések

A request nem null szöveges vagy JSON objektum/tömb state-et és nem üres question-ID mapet tartalmaz. Az azonosítók nem üresek, a primitív diszkriminátor kötelező. Nem véges JSON számot nem engedünk át.

- Choice: nem üres instructions, legalább két opció és opcionális szöveges leírás. Eredménye választás, opció szerinti valószínűségek és confidence.
- Score: 2–10 rendezett, nem üres szöveges szint. Az első szint indexe 0. Eredménye törtértéket is megőrző score, egész indexű eloszlás és confidence.
- Noul: nem üres instructions, opcionális true/false szöveges kritériumok. A noul önmagában valószínűség, nincs hozzáadott confidence.

A result pontosan a kért question-ID-kra ad azonos primitívű választ. A Choice kiválasztása és eloszláskulcsai a megadott opciókhoz tartoznak. A Score és az eloszlás indexei a megadott skálán belüliek. Minden probability/confidence véges és 0–1 közötti. Hibás vagy hiányzó eredményt nem egészítünk ki alapértelmezett döntéssé. A model, opcionális provider request ID és tokenhasználat megmarad. A numerikus értékeket nem kerekítjük, confidence-ből nem következik végrehajtási engedély.

## Adapterek

A MockDecisionAdapter teljes request alapján kulcsolt, explicit fixture-öket használ. Nincs hálózat, véletlenszám vagy automatikus válaszgenerálás. Azonos request és fixture azonos eredményt ad. Hiányzó vagy hibás fixture DecisionInvalidResponseError. Tesztek domain hibát is beállíthatnak. A szintetikus probability és confidence nem a Jev pontosságának mérése.

The live SDK adapter and provider are introduced in FND-019.
