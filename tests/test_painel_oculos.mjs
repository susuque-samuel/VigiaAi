// Testes de apresentação em memória: sem navegador, porta HTTP ou câmera.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";

class Elemento {
  constructor() {
    this.children = [];
    this.textContent = "";
    this.classList = { toggle() {} };
  }
  append(...itens) { this.children.push(...itens); }
  replaceChildren(...itens) { this.children = [...itens]; }
  insertRow() { const item = new Elemento(); this.append(item); return item; }
  insertCell() { const item = new Elemento(); this.append(item); return item; }
  addEventListener() {}
}

async function painel() {
  const js = await readFile(new URL("../static/painel.js", import.meta.url), "utf8");
  const elementos = new Map();
  const obter = (id) => {
    if (!elementos.has(id)) elementos.set(id, new Elemento());
    return elementos.get(id);
  };
  const status = {
    estado: "ativo", executando: true, mensagem: "Simulação", epi_obrigatorio: ["oculos"],
    epi_ativo: true, epis_suportados: ["oculos"], oculos_ativo: true,
    epi_reanalises: 1, epi_pessoas_pendentes: 2, deteccoes: [], eventos: [],
  };
  const contexto = vm.createContext({
    document: { getElementById: obter, createElement: () => new Elemento(), querySelectorAll: () => [] },
    AbortController, URL, console, setTimeout: () => 1, clearTimeout() {},
    fetch: async (url) => {
      assert.ok(["/amostras", "/status"].includes(url));
      return { ok: true, json: async () => url === "/amostras" ? { total: 0, amostras: [] } : status };
    },
  });
  vm.runInContext(js, contexto);
  await vm.runInContext("atualizarStatus()", contexto);
  return { obter, executar: (codigo) => vm.runInContext(codigo, contexto) };
}

test("mostra motivo por item sem marcar inconclusivo como presença", async () => {
  const { obter, executar } = await painel();
  executar("mostrarPessoas([{id:1,postura:null,epis:{oculos:'inconclusivo'},epis_motivos:{oculos:'Detalhe insuficiente: 44 px na imagem original.'}}])");
  const card = obter("pessoas").children[0];
  assert.match(card.children[1].textContent, /^Óculos: inconclusivo$/);
  assert.match(card.children[2].textContent, /44 px na imagem original/);
});

test("não exibe motivo antigo depois de detectar presença", async () => {
  const { obter, executar } = await painel();
  executar("mostrarPessoas([{id:1,postura:'Em pe',epis:{oculos:'presente'},epis_motivos:{oculos:'motivo antigo'}}])");
  const card = obter("pessoas").children[0];
  assert.equal(card.children.some((item) => item.textContent.includes("motivo antigo")), false);
  assert.match(card.children[1].textContent, /detectado/);
});

test("continua aceitando status antigo sem campo de motivos", async () => {
  const { obter, executar } = await painel();
  executar("mostrarPessoas([{id:1,postura:null,epis:{oculos:'inconclusivo'}}])");
  assert.match(obter("pessoas").children[0].children[1].textContent, /inconclusivo/);
});

test("explica verificação auxiliar e pessoas pendentes sem prometer ausência", async () => {
  const { obter } = await painel();
  assert.match(obter("epiStatus").textContent, /verificação adicional ativa/);
  assert.match(obter("epiStatus").textContent, /Aguardando reanálise: 2/);
  assert.match(obter("epiStatus").textContent, /não comprovam ausência/);
});
