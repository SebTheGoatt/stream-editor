// Channel intro sting for Seb The Goat: 2.5 s, 1920x1080, 30 fps.
// Rendered headless with EffectCraft:  effectcraft-cli script intro.jsx --empty --save-as intro.ecproj
var comp = app.project.items.addComp("Intro", 1920, 1080, 1, 2.5, 30);
var bg = comp.layers.addSolid([0.06, 0.06, 0.08], "BG", 1920, 1080, 1);

// Gold slash wipe behind the title.
var bar = comp.layers.addSolid([1, 0.83, 0], "Bar", 2400, 260, 1);
bar.property("Transform").property("Rotation").setValue(-6);
var bp = bar.property("Transform").property("Position");
bp.setValueAtTime(0.0, [-1400, 540]);
bp.setValueAtTime(0.25, [960, 540]);
bp.setValueAtTime(2.2, [960, 540]);
bp.setValueAtTime(2.5, [3300, 540]);

function title(txt, size, color, y, tIn) {
  var l = comp.layers.addText(txt);
  var st = l.property("Source Text");
  var d = st.value;
  d.font = "Anton-Regular";
  d.fontSize = size;
  d.fillColor = color;
  d.applyStroke = true;
  d.strokeColor = [0, 0, 0];
  d.strokeWidth = size / 14;
  d.justification = ParagraphJustification.CENTER_JUSTIFY;
  st.setValue(d);
  var tr = l.property("Transform");
  tr.property("Position").setValue([960, y]);
  var s = tr.property("Scale");
  s.setValueAtTime(tIn, [0, 0]);
  s.setValueAtTime(tIn + 0.15, [125, 125]);
  s.setValueAtTime(tIn + 0.28, [100, 100]);
  s.setValueAtTime(2.2, [100, 100]);
  s.setValueAtTime(2.5, [0, 0]);
  return l;
}

var main = title("SEB THE GOAT", 230, [1, 1, 1], 600, 0.2);
// Camera-shake feel on the title once it lands.
main.property("Transform").property("Position").expression =
  "time > 0.35 && time < 0.8 ? wiggle(30, 14) : value";
var sub = title("CERTIFIED GAMER (ALLEGEDLY)", 70, [1, 1, 1], 790, 0.45);
