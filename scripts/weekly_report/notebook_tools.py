"""Shared notebook navigation. Keep the weekly and monthly copies identical.

Only navigation markup is emitted; no report data or runtime state is touched.
"""
TOOLS_LINKS = (
    ("OKR Tracker", "https://okr.headout.com/okr-tracker"),
    ("Churn Tracker", "https://okr.headout.com/band-explorer?focus=reverse-kr"),
    ("All CEs Trend", "https://all-ces-trend.vercel.app/"),
    ("CE Trends", "https://eos.headout.com/ce-trends"),
)


def render_tools_nav():
    links = "".join(
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">'
        f'{label}<span aria-hidden="true">↗</span>'
        '<span class="notebook-tools-sr"> (opens in a new tab)</span></a>'
        for label, url in TOOLS_LINKS
    )
    return """
<style id="notebook-tools-style">
.notebook-nav-row{flex-wrap:wrap}
.notebook-tools{position:relative;flex:none;align-self:center;color:#1C1726;font:600 13px 'Hanken Grotesk',system-ui,sans-serif}
.notebook-tools>summary{display:flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:0 14px;list-style:none;cursor:pointer;border:1px solid #E7E1F1;border-radius:10px;background:#fff;color:#6B00D6;user-select:none}
.notebook-tools>summary::-webkit-details-marker{display:none}
.notebook-tools>summary:hover,.notebook-tools[open]>summary{background:#F3E8FF;border-color:#CFA7FF}
.notebook-tools>summary:focus-visible,.notebook-tools a:focus-visible{outline:2px solid #8000FF;outline-offset:2px}
.notebook-tools[open] .notebook-tools-chevron{transform:rotate(180deg)}
.notebook-tools nav{position:absolute;z-index:5;right:0;top:calc(100% + 8px);width:244px;max-width:calc(100vw - 32px);max-height:calc(100dvh - 180px);overflow:auto;padding:6px;border:1px solid #E7E1F1;border-radius:16px;background:#fff;box-shadow:0 8px 24px rgb(28 23 38 / .15)}
.notebook-tools a{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:44px;padding:10px;border-radius:10px;color:#1C1726;text-decoration:none;white-space:nowrap}
.notebook-tools a:hover{background:#F3E8FF;color:#6B00D6}
.notebook-tools-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;border:0}
@media(max-width:640px){.notebook-nav-row{gap:10px!important;padding:12px 16px!important}.notebook-tools{margin-left:auto}}
@media print{.notebook-tools{display:none}}
</style>
<details class="notebook-tools" id="notebook-tools">
  <summary>Tools <span class="notebook-tools-chevron" aria-hidden="true">⌄</span></summary>
  <nav aria-label="Related dashboards">""" + links + """</nav>
</details>
<script>
(function(){
  const tools=document.getElementById('notebook-tools');
  document.addEventListener('click',function(event){
    if(tools.open&&!tools.contains(event.target))tools.open=false;
  });
  document.addEventListener('keydown',function(event){
    if(event.key==='Escape'&&tools.open){
      tools.open=false;tools.querySelector('summary').focus();
      event.preventDefault();event.stopPropagation();
    }
  },true);
  tools.querySelectorAll('a').forEach(function(link){
    link.addEventListener('click',function(){tools.open=false;});
  });
})();
</script>"""

