from pathlib import Path
from datetime import datetime
import shutil
import sys

PROJECT = Path(r"C:\Users\Kane\Documents\Projects\Cylinder_Quote_To_HTML\Cylinder_Quote_Web_Milestone_1")
CSS = PROJECT / "app" / "static" / "styles.css"
JS = PROJECT / "app" / "static" / "app.js"

print("=" * 78)
print("JIT CYLINDER QUOTE - ORDERENTRY REPLICA v1.2 PROPORTIONAL SCALE PATCH")
print("=" * 78)

if not PROJECT.exists():
    print(f"ERROR: Project folder was not found:\n{PROJECT}")
    input("Press Enter to close...")
    sys.exit(1)

for path in (CSS, JS):
    if not path.exists():
        print(f"ERROR: Required file was not found:\n{path}")
        input("Press Enter to close...")
        sys.exit(1)

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
for path in (CSS, JS):
    backup = path.with_name(path.name + f".before_v1_2_{stamp}.bak")
    shutil.copy2(path, backup)

css = CSS.read_text(encoding="utf-8")
# Remove the previous v1.1 enlargement override. The original replica geometry
# is retained, then the whole form is scaled uniformly by v1.2.
v11_marker = "/* OrderEntry Replica v1.1: fill the browser workspace while preserving the legacy geometry. */"
if v11_marker in css:
    css = css.split(v11_marker)[0].rstrip() + "\n"

v12_marker = "/* OrderEntry Replica v1.2 - proportional viewport scaling."
if v12_marker in css:
    css = css.split(v12_marker)[0].rstrip() + "\n"

css += r'''

/* OrderEntry Replica v1.2 - proportional viewport scaling.
   The form keeps one fixed design geometry and the browser scales the entire
   interface uniformly. Fonts, controls, spacing, tabs and buttons therefore
   grow/shrink together without horizontal stretching. */
html,body{
  width:100%;
  height:100%;
  overflow:hidden;
}
body{
  margin:0;
  padding:0;
  position:relative;
  background:#e8e8e8;
}
.orderentry-window{
  width:1360px;
  max-width:none;
  min-width:0;
  margin:0;
  position:absolute;
  left:0;
  top:0;
  transform-origin:top left;
  will-change:transform,left,top;
}
/* Keep Discount / Net Each / Profit well clear of Quote. */
.pricing-rows{
  width:330px;
  margin:22px 255px 0 auto;
  gap:9px;
}
.quote-button{
  right:30px;
  bottom:46px;
  width:132px;
  height:78px;
}
.engineering-panel::after{
  content:"";
  position:absolute;
  right:188px;
  bottom:38px;
  width:1px;
  height:118px;
  background:#999;
  opacity:.7;
}
@media(max-width:1050px){
  body{overflow:hidden}
  .orderentry-window{min-width:0}
}
'''
CSS.write_text(css, encoding="utf-8")
print("Updated: app/static/styles.css")

js = JS.read_text(encoding="utf-8")
js_marker = "/* OrderEntry Replica v1.2 proportional scaling */"
if js_marker in js:
    js = js.split(js_marker)[0].rstrip() + "\n"

js += r'''

/* OrderEntry Replica v1.2 proportional scaling */
function scaleOrderEntryToViewport() {
  const win = document.querySelector('.orderentry-window');
  if (!win) return;

  // offsetWidth/offsetHeight are the unscaled design dimensions.
  const designWidth = win.offsetWidth;
  const designHeight = win.offsetHeight;
  if (!designWidth || !designHeight) return;

  const edge = 10;
  const availableWidth = Math.max(1, window.innerWidth - edge * 2);
  const availableHeight = Math.max(1, window.innerHeight - edge * 2);
  const scale = Math.min(availableWidth / designWidth, availableHeight / designHeight);

  const renderedWidth = designWidth * scale;
  const renderedHeight = designHeight * scale;
  const left = Math.max(edge, (window.innerWidth - renderedWidth) / 2);
  const top = Math.max(edge, (window.innerHeight - renderedHeight) / 2);

  win.style.transform = `scale(${scale})`;
  win.style.left = `${left}px`;
  win.style.top = `${top}px`;
}

let orderEntryScaleFrame = 0;
function queueOrderEntryScale() {
  cancelAnimationFrame(orderEntryScaleFrame);
  orderEntryScaleFrame = requestAnimationFrame(scaleOrderEntryToViewport);
}

window.addEventListener('resize', queueOrderEntryScale);
window.addEventListener('load', queueOrderEntryScale);

const orderEntryWindow = document.querySelector('.orderentry-window');
if (orderEntryWindow && 'ResizeObserver' in window) {
  new ResizeObserver(queueOrderEntryScale).observe(orderEntryWindow);
}
queueOrderEntryScale();
'''
JS.write_text(js, encoding="utf-8")
print("Updated: app/static/app.js")

print()
print("SUCCESS: OrderEntry Replica v1.2 proportional scaling is installed.")
print("- The whole form now grows/shrinks at one uniform ratio.")
print("- Font, controls, spacing and buttons scale together.")
print("- The form stays inside both browser width and browser height.")
print("- Discount / Net Each / Profit were moved left away from Quote.")
print("- Blank-slate/reset behavior and Pricing Engine v1.2 were not replaced.")
print()
print("Restart RUN_CYLINDER_QUOTE.bat, then refresh the browser (Ctrl+F5 if needed).")
input("Press Enter to close...")
