// "LIKE + SUBSCRIBE" pop-up (M3RKMUS1C style), 3.5 s, 1920x1080, transparent background.
// Render headless with EffectCraft:
//   effectcraft-cli script intro/subscribe.jsx --empty --save-as intro/subscribe.ecproj
//   effectcraft-cli render --project intro/subscribe.ecproj --comp Subscribe --out brand/subscribe.mov \
//       --format prores --prores 4444 --channels rgba --audio off
var comp = app.project.items.addComp("Subscribe", 1920, 1080, 1, 3.5, 30);
var X = 960, Y = 930;          // button centre, bottom middle of the frame
var IN = 0.0, CLICK = 1.6, OUT = 3.0;

function slide(layer, dx, dy) {
  var p = layer.property("Transform").property("Position");
  p.setValueAtTime(IN, [X + dx, 1250 + dy]);
  p.setValueAtTime(IN + 0.22, [X + dx, Y - 18 + dy]);   // overshoot
  p.setValueAtTime(IN + 0.34, [X + dx, Y + dy]);
  p.setValueAtTime(OUT, [X + dx, Y + dy]);
  p.setValueAtTime(OUT + 0.35, [X + dx, 1300 + dy]);
}

function click(layer) {
  // The "press": a quick squash right at the click.
  var s = layer.property("Transform").property("Scale");
  s.setValueAtTime(CLICK - 0.08, [100, 100]);
  s.setValueAtTime(CLICK, [90, 90]);
  s.setValueAtTime(CLICK + 0.1, [104, 104]);
  s.setValueAtTime(CLICK + 0.18, [100, 100]);
}

var FRAME = 1 / 30;  // keys closer than a frame merge, so hard switches use a one-frame step

function fade(layer, on, off) {
  var o = layer.property("Transform").property("Opacity");
  if (on > 0) {
    o.setValueAtTime(0, 0);
    o.setValueAtTime(on - FRAME, 0);
  }
  o.setValueAtTime(on, 100);
  if (off !== undefined) {
    o.setValueAtTime(off - FRAME, 100);
    o.setValueAtTime(off, 0);
  }
}

function label(txt, size, color, stroke) {
  var l = comp.layers.addText(txt);
  var st = l.property("Source Text");
  var d = st.value;
  d.font = "Anton-Regular";
  d.fontSize = size;
  d.fillColor = color;
  d.applyStroke = stroke;
  d.strokeColor = [0, 0, 0];
  d.strokeWidth = stroke ? size / 12 : 0;
  d.justification = ParagraphJustification.CENTER_JUSTIFY;
  st.setValue(d);
  return l;
}

// Button: red until the click, then grey "SUBSCRIBED".
var grey = comp.layers.addSolid([0.33, 0.33, 0.35], "Subscribed", 560, 120, 1);
slide(grey, 0, 0); click(grey); fade(grey, CLICK);
var red = comp.layers.addSolid([0.90, 0.13, 0.09], "Subscribe", 560, 120, 1);
slide(red, 0, 0); click(red); fade(red, 0, CLICK);

var t1 = label("SUBSCRIBE", 86, [1, 1, 1], false);
slide(t1, 0, 32); click(t1); fade(t1, 0, CLICK);
var t2 = label("SUBSCRIBED", 86, [0.85, 0.85, 0.85], false);
slide(t2, 0, 32); click(t2); fade(t2, CLICK);

// Yellow "LIKE +" tag that pops in just after the button lands.
var like = label("LIKE +", 64, [1, 0.83, 0], true);
var lp = like.property("Transform").property("Position");
lp.setValue([X - 395, Y + 24]);
var ls = like.property("Transform").property("Scale");
ls.setValueAtTime(0.30, [0, 0]);
ls.setValueAtTime(0.45, [125, 125]);
ls.setValueAtTime(0.55, [100, 100]);
ls.setValueAtTime(OUT, [100, 100]);
ls.setValueAtTime(OUT + 0.2, [0, 0]);
