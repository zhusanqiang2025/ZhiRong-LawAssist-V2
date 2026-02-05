import {
  parse
} from "./chunk-FPZUDIIY.js";
import "./chunk-2LCDP2AZ.js";
import "./chunk-R3QO2ASY.js";
import "./chunk-D25RZWOE.js";
import "./chunk-F6SSHYQZ.js";
import "./chunk-Q7V3RZ75.js";
import "./chunk-CPHAU6P2.js";
import "./chunk-3YGP4RUS.js";
import "./chunk-JU4N7ASV.js";
import "./chunk-F6R2U5QB.js";
import {
  package_default
} from "./chunk-WAEKFLGE.js";
import {
  selectSvgElement
} from "./chunk-VCMIJN4Q.js";
import {
  configureSvgSize
} from "./chunk-7KB542JL.js";
import {
  __name,
  log
} from "./chunk-TXYUMXJC.js";
import "./chunk-XHPT6X5E.js";
import "./chunk-AHDI4WSU.js";
import "./chunk-TXBF2BBY.js";
import "./chunk-GWVER62F.js";
import "./chunk-IKZWERSR.js";

// node_modules/mermaid/dist/chunks/mermaid.core/infoDiagram-WHAUD3N6.mjs
var parser = {
  parse: __name(async (input) => {
    const ast = await parse("info", input);
    log.debug(ast);
  }, "parse")
};
var DEFAULT_INFO_DB = {
  version: package_default.version + (true ? "" : "-tiny")
};
var getVersion = __name(() => DEFAULT_INFO_DB.version, "getVersion");
var db = {
  getVersion
};
var draw = __name((text, id, version) => {
  log.debug("rendering info diagram\n" + text);
  const svg = selectSvgElement(id);
  configureSvgSize(svg, 100, 400, true);
  const group = svg.append("g");
  group.append("text").attr("x", 100).attr("y", 40).attr("class", "version").attr("font-size", 32).style("text-anchor", "middle").text(`v${version}`);
}, "draw");
var renderer = { draw };
var diagram = {
  parser,
  db,
  renderer
};
export {
  diagram
};
//# sourceMappingURL=infoDiagram-WHAUD3N6-BVL4ZRUM.js.map
