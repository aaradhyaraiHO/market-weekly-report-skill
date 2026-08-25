#!/usr/bin/env python3
"""
Inject the live Review tab into deployed weekly-report-*.html shells.

The V2 shell (market-notebook-v2/weekly-report-<slug>.html) is a hand-authored, self-contained page
whose whole app lives in one IIFE. This script wires the Review tab (from
docs/weekly-review/final-wbr-review-mode.html) into it, backed by the live /api/review endpoints:

  1. Enables the "Review" rail button (data-report-view="review").
  2. Inserts an empty <section id="review-view" class="report-view" hidden> container.
  3. Patches the view-switcher so Review toggles like Overview / All CEs and calls window.__rv.onShow().
  4. Inlines review-view.css + review-client.js + review-view.js, then boots initReviewView() from
     inside the shell IIFE so it can pass the closure refs (currentHeadline, helpers, openCeDrawer).

Idempotent: safe to re-run. Each run strips the previously injected style/boot blocks and re-inlines
the current source, so editing review/review-view.{css,js} + re-running redeploys the change.

Usage:
    python3 inject_review_view.py <deploy_dir>/weekly-report-north-america.html [more.html ...]
    python3 inject_review_view.py --market north_america            # resolves the current alias
    python3 inject_review_view.py --all                              # every weekly-report-*.html alias
Deploy after (USER, from ~/analytics):  vercel deploy --prod --cwd market-notebook-v2
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW_DIR = HERE / "review"
DEFAULT_DEPLOY = Path(os.path.expanduser(os.environ.get("MMR_NOTEBOOK_DIR", "~/analytics/market-notebook-v2")))

STYLE_ID = "rv-style"
BOOT_START = "/*RV-BOOT-START*/"
BOOT_END = "/*RV-BOOT-END*/"

NAV_RE = re.compile(r'<button class="nav-item"[^>]*>Review</button>')
NAV_ENABLED = '<button class="nav-item" type="button" data-report-view="review">Review</button>'

# insertion anchor: the all-ces section close + main close. We slot the review-view container
# between them so it is a sibling of #overview-view / #all-ces-view *inside* <main>.
CONTAINER_ANCHOR = '      </section>\n    </main>'
CONTAINER_HTML = ('      </section>\n'
                  '      <section class="report-view" id="review-view" hidden aria-label="Weekly review"></section>\n'
                  '    </main>')

# view-switch: the shell toggles overview + all-ces; we add review right after the all-ces toggle.
SWITCH_ANCHOR = "document.getElementById('all-ces-view').hidden=view!=='all-ces';"
SWITCH_ADD = ("document.getElementById('all-ces-view').hidden=view!=='all-ces';"
              "var _rv=document.getElementById('review-view');if(_rv)_rv.hidden=view!=='review';"
              "if(view==='review'&&window.__rv)window.__rv.onShow();")

# the shell's IIFE ends with these three calls then `})();` — we boot just before the close.
BOOT_ANCHOR = "      actionPrevPull();\n    })();"
CE_REVIEW_CONTROL = '<button class="drawer-omni" id="ce-open-review" type="button">Open in Review →</button>'
CE_REVIEW_CONTROL_ANCHOR = '<a class="drawer-omni" id="ce-drawer-omni"'
CE_REVIEW_WIRE_ANCHOR = "document.getElementById('ce-drawer-omni').href=omniLink(ce.ce_id);"
CE_REVIEW_WIRE = CE_REVIEW_WIRE_ANCHOR + "document.getElementById('ce-open-review').onclick=()=>{if(window.__openReviewCe)window.__openReviewCe(String(ce.ce_id));};"


def _read(path: Path) -> str:
    if not path.exists():
        sys.exit(f"missing asset: {path}")
    return path.read_text()


def _guard(js: str, label: str) -> str:
    if "</script" in js.lower():
        sys.exit(f"{label} contains a </script> sequence — cannot inline safely")
    return js


APP_DIR = HERE / "review-app"


def stage_review_api(deploy: Path) -> None:
    """Stage only the isolated Review routes beside the injected UI.

    The V1/V2 diagnostic actions route is deliberately excluded: it remains
    whatever the complete Market Notebook artifact already uses.  Keeping
    these copies in the same release command prevents a Preview from pairing a
    new Review UI with an old Granola/Review proxy implementation.
    """
    api_dir = deploy / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    notes = HERE / "notes"
    routes = {
        "review_proxy_api.js": "review.js",
        "review_summary_api.js": "review-summary.js",
        "granola_link_api.js": "granola-link.js",
    }
    for source, target in routes.items():
        shutil.copyfile(notes / source, api_dir / target)


def build_boot(deploy: Path, native: bool = False):
    if native:
        css = _read(APP_DIR / "node_modules/@headout/pixie/styles.css")
        view_js = _guard(_read(APP_DIR / "dist/review-view.js"), "native bundle")
        client_js = ""  # the native bundle has its own /api/review client
        style = f'<style id="{STYLE_ID}">\n{css}\n</style>'
        boot = (
            f"{BOOT_START}\n"
            "try{\n"
            "/* --- inlined native Eevee bundle (React + @headout/eevee) --- */\n"
            f"{view_js}\n"
            "if(window.initReviewView){\n"
            "  window.__rv=window.initReviewView({\n"
            "    root:document.getElementById('review-view'),\n"
            "    getHeadline:function(){var h=currentHeadline(); var c=(typeof payload!=='undefined'&&payload.notes_channels)||h.notes_channels||{}; return Object.assign({},h,{notes_channels:c});}, getBaseHeadline:function(){var h=baseHeadline(); var c=(typeof payload!=='undefined'&&payload.notes_channels)||h.notes_channels||{}; return Object.assign({},h,{notes_channels:c});},\n"
            "    openCeDrawer:(typeof openCeDrawer!=='undefined'?openCeDrawer:null)\n"
            "  });\n"
            "  window.__openReviewCe=function(ceId){if(typeof closeCeDrawer==='function')closeCeDrawer();var b=document.querySelector('[data-report-view=\"review\"]');if(b)b.click();if(window.__rv&&window.__rv.focusCe)window.__rv.focusCe(String(ceId));};\n"
            "  setTimeout(function(){window.__rv&&window.__rv.prefetch&&window.__rv.prefetch();},250);\n"
            "  if(typeof weekSelect!=='undefined'&&weekSelect)weekSelect.addEventListener('change',function(){window.__rv&&window.__rv.onWeekChange&&window.__rv.onWeekChange();});\n"
            "}\n"
            "}catch(_rvErr){console.warn('native review view init failed',_rvErr);}\n"
            f"{BOOT_END}"
        )
        return style, boot
    css = _read(REVIEW_DIR / "review-view.css")
    view_js = _guard(_read(REVIEW_DIR / "review-view.js"), "review-view.js")
    # The browser client is source-controlled beside the Review backend. Do not
    # source it from a deploy directory: doing so can silently inject a stale
    # client whose route contract no longer matches the canonical UI.
    client_path = HERE / "notes" / "review_client.js"
    client_js = _guard(_read(client_path), "review-client.js")
    style = f'<style id="{STYLE_ID}">\n{css}\n</style>'
    boot = (
        f"{BOOT_START}\n"
        "try{\n"
        "/* --- inlined review-client.js --- */\n"
        f"{client_js}\n"
        "/* --- inlined review-view.js --- */\n"
        f"{view_js}\n"
        "if(window.initReviewView){\n"
        "  window.__rv=window.initReviewView({\n"
        "    root:document.getElementById('review-view'),\n"
        "    getHeadline:function(){var h=currentHeadline(); var c=(typeof payload!=='undefined'&&payload.notes_channels)||h.notes_channels||{}; return Object.assign({},h,{notes_channels:c});}, getBaseHeadline:function(){var h=baseHeadline(); var c=(typeof payload!=='undefined'&&payload.notes_channels)||h.notes_channels||{}; return Object.assign({},h,{notes_channels:c});},\n"
        "    helpers:{escapeHtml:escapeHtml, money:money, pct:pct,\n"
        "      tone:(typeof tone!=='undefined'?tone:null),\n"
        "      signedMoney:(typeof signedMoney!=='undefined'?signedMoney:null),\n"
        "      dateLabel:(typeof dateLabel!=='undefined'?dateLabel:null),\n"
        "      omniLink:(typeof omniLink!=='undefined'?omniLink:null),\n"
        "      count:(typeof count!=='undefined'?count:null)},\n"
        "    openCeDrawer:(typeof openCeDrawer!=='undefined'?openCeDrawer:null)\n"
        "  });\n"
        "  window.__openReviewCe=function(ceId){if(typeof closeCeDrawer==='function')closeCeDrawer();var b=document.querySelector('[data-report-view=\"review\"]');if(b)b.click();if(window.__rv&&window.__rv.focusCe)window.__rv.focusCe(String(ceId));};\n"
        "  setTimeout(function(){window.__rv&&window.__rv.prefetch&&window.__rv.prefetch();},250);\n"
        "  if(typeof weekSelect!=='undefined'&&weekSelect)weekSelect.addEventListener('change',function(){window.__rv&&window.__rv.onWeekChange();});\n"
        "}\n"
        "}catch(_rvErr){console.warn('review view init failed',_rvErr);}\n"
        f"{BOOT_END}"
    )
    return style, boot


def strip_previous(html: str) -> str:
    html = re.sub(rf'<style id="{STYLE_ID}">.*?</style>\n?', "", html, flags=re.S)
    # Remove the boot block AND the surrounding whitespace, normalizing back to the bare
    # anchor (`actionPrevPull();\n    })();`) so re-injection always finds it.
    html = re.sub(r"\n\s*" + re.escape(BOOT_START) + r".*?" + re.escape(BOOT_END) + r"\s*\n",
                  "\n", html, flags=re.S)
    return html


def inject(path: Path, deploy: Path, native: bool = False) -> bool:
    html = path.read_text()
    if "report-data" not in html or "data-report-view" not in html:
        print(f"  ! {path.name}: not a V2 shell (no report-data / nav) — skipped")
        return False

    style, boot = build_boot(deploy, native)
    html = strip_previous(html)

    # 1. nav button
    if not NAV_RE.search(html):
        print(f"  ! {path.name}: Review nav button not found — skipped")
        return False
    html = NAV_RE.sub(NAV_ENABLED, html, count=1)

    # 2. container (only once)
    if 'id="review-view"' not in html:
        if CONTAINER_ANCHOR not in html:
            print(f"  ! {path.name}: container anchor not found — skipped")
            return False
        html = html.replace(CONTAINER_ANCHOR, CONTAINER_HTML, 1)

    # 3. view-switch
    if "getElementById('review-view')" not in html:
        if SWITCH_ANCHOR not in html:
            print(f"  ! {path.name}: view-switch anchor not found — skipped")
            return False
        html = html.replace(SWITCH_ANCHOR, SWITCH_ADD, 1)

    # Existing complete static V2 artifacts predate the drawer → Review control.
    # Add it to the existing drawer rather than rebuilding any report analytics.
    if 'id="ce-open-review"' not in html:
        if CE_REVIEW_CONTROL_ANCHOR not in html:
            print(f"  ! {path.name}: CE drawer identity anchor not found — skipped")
            return False
        html = html.replace(CE_REVIEW_CONTROL_ANCHOR, CE_REVIEW_CONTROL + CE_REVIEW_CONTROL_ANCHOR, 1)
    if "getElementById('ce-open-review').onclick" not in html:
        if CE_REVIEW_WIRE_ANCHOR not in html:
            print(f"  ! {path.name}: CE drawer Review wire anchor not found — skipped")
            return False
        html = html.replace(CE_REVIEW_WIRE_ANCHOR, CE_REVIEW_WIRE, 1)

    # 4. style before </head>
    html = html.replace("</head>", style + "\n</head>", 1)

    # 5. boot before the IIFE close
    if BOOT_ANCHOR not in html:
        print(f"  ! {path.name}: boot anchor not found — skipped")
        return False
    html = html.replace(BOOT_ANCHOR, "      actionPrevPull();\n\n" + boot + "\n    })();", 1)

    path.write_text(html)
    print(f"  ✓ {path.name}: Review tab injected ({path.stat().st_size // 1024} KB)")
    return True


def resolve_targets(args) -> list[Path]:
    deploy = Path(os.path.expanduser(args.deploy)) if args.deploy else DEFAULT_DEPLOY
    if args.files:
        return [Path(f) for f in args.files]
    if args.all:
        # Current aliases and dated report archives are both user-facing
        # reports.  A report opened from Weekly history must never fall back to
        # the old disabled Review placeholder.
        return sorted(deploy.glob("weekly-report-*.html"))
    if args.market:
        slug = args.market.replace("_", "-")
        return [deploy / f"weekly-report-{slug}.html"]
    sys.exit("provide file paths, --market <slug>, or --all")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inject the live Review tab into weekly-report shells")
    ap.add_argument("files", nargs="*", help="explicit HTML file paths")
    ap.add_argument("--market", help="market slug (current-week alias)")
    ap.add_argument("--all", action="store_true", help="all current and dated report pages in the deploy dir")
    ap.add_argument("--deploy", help="deploy dir (default: ~/analytics/market-notebook-v2 or $MMR_NOTEBOOK_DIR)")
    ap.add_argument("--native", action="store_true", help="inject the native React/Eevee bundle + pixie.css instead of the vanilla view")
    args = ap.parse_args(argv)
    deploy = Path(os.path.expanduser(args.deploy)) if args.deploy else DEFAULT_DEPLOY

    stage_review_api(deploy)

    targets = resolve_targets(args)
    print(f"Inject Review tab · {len(targets)} file(s)\n  assets: {REVIEW_DIR}\n  deploy: {deploy}")
    done = 0
    for path in targets:
        if not path.exists():
            print(f"  ! {path} not found — skipped")
            continue
        if inject(path, deploy, args.native):
            done += 1
    print(f"\n  injected {done}/{len(targets)} file(s)")
    if done:
        print("  next (USER, from ~/analytics):  vercel deploy --prod --cwd market-notebook-v2")


if __name__ == "__main__":
    main()
