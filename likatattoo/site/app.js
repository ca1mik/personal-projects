function formatRub(value) {
  return `${Math.round(value).toLocaleString("ru-RU")} ₽`;
}

function readNumber(id) {
  const element = document.getElementById(id);
  return Number(element?.value || 0);
}

function renderFinance() {
  const clients = readNumber("clients");
  const avgCheck = readNumber("avgCheck");
  const supplies = readNumber("supplies");
  const coworking = readNumber("coworking");

  const revenue = clients * avgCheck;
  const directCosts = clients * (supplies + coworking);
  const grossProfit = revenue - directCosts;

  document.getElementById("revenue").textContent = formatRub(revenue);
  document.getElementById("directCosts").textContent = formatRub(directCosts);
  document.getElementById("grossProfit").textContent = formatRub(grossProfit);
}

for (const id of ["clients", "avgCheck", "supplies", "coworking"]) {
  document.getElementById(id)?.addEventListener("input", renderFinance);
}

renderFinance();
