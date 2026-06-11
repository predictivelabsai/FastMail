"""FastMail 3-pane layout: folders · message list/reading · AI rail."""
from __future__ import annotations

from fasthtml.common import (
    Div, H1, H3, H4, P, Span, A, Button, Form, Input, Title, Link, Script, Style, NotStr,
)

import db

LAYOUT_CSS = """
:root{
  --bg:#f6f5fb; --surface:#ffffff; --surface-2:#f0eefa; --border:#e4e0f1; --text:#1f1933;
  --text-dim:#4e4763; --text-mute:#8b84a3; --accent:#7c3aed; --accent-hover:#6d28d9;
  --accent-light:#ede9fe; --ok:#16a34a; --warn:#d97706; --danger:#e11d48; --star:#f59e0b;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;height:100%;background:var(--bg);color:var(--text);
  font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:14px;}
a{color:var(--accent);text-decoration:none;} a:hover{text-decoration:underline;}
.app{display:grid;grid-template-columns:240px 1fr var(--rail,340px);grid-template-rows:52px 1fr;
  grid-template-areas:"top top top" "left center right";height:100vh;overflow:hidden;transition:grid-template-columns .18s ease;}
.app.right-expanded{--rail:clamp(420px,42vw,720px);} .app.right-collapsed{--rail:0px;} .app.right-collapsed .right-pane{display:none;}
#copilot-reopen{position:fixed;right:0;bottom:26px;display:none;align-items:center;gap:6px;cursor:pointer;z-index:60;
  background:var(--accent);color:#fff;font-size:13px;font-weight:600;padding:9px 14px;border-radius:8px 0 0 8px;box-shadow:0 2px 10px rgba(0,0,0,.18);}
.app.right-collapsed #copilot-reopen{display:inline-flex;}
.copilot-min,.copilot-exp{cursor:pointer;border:1px solid var(--border);background:var(--surface);border-radius:6px;padding:4px 9px;font-size:13px;line-height:1;color:var(--text-mute);}
.topbar{grid-area:top;display:flex;align-items:center;justify-content:space-between;padding:0 20px;background:var(--surface);border-bottom:1px solid var(--border);}
.brand{font-weight:700;letter-spacing:.3px;display:flex;align-items:center;gap:8px;font-size:16px;}
.brand-dot{width:11px;height:11px;background:var(--accent);border-radius:3px;display:inline-block;}
.env-pill{background:var(--accent-light);color:var(--accent-hover);padding:3px 10px;border-radius:999px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;}
.topbar .actions{display:flex;gap:10px;align-items:center;} .topbar .who{color:var(--text-mute);font-size:12px;}
.left-pane{grid-area:left;background:var(--surface);border-right:1px solid var(--border);padding:12px 0;overflow-y:auto;}
.compose-btn{display:block;margin:0 16px 12px;text-align:center;background:var(--accent);color:#fff;font-weight:600;padding:10px;border-radius:10px;}
.compose-btn:hover{background:var(--accent-hover);color:#fff;text-decoration:none;}
.nav-section{margin-bottom:14px;} .nav-section h4{margin:6px 16px 4px;font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--text-mute);font-weight:700;}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 16px;color:var(--text-dim);cursor:pointer;border-left:3px solid transparent;}
.nav-item:hover{background:var(--surface-2);color:var(--text);text-decoration:none;}
.nav-item.active{background:var(--accent-light);color:var(--accent-hover);border-left-color:var(--accent);font-weight:600;}
.nav-item .badge{margin-left:auto;font-size:11px;background:var(--accent);color:#fff;border-radius:999px;padding:1px 7px;font-weight:700;}
.nav-item .cnt{margin-left:auto;font-size:11px;color:var(--text-mute);}
.nav-icon{width:18px;display:inline-block;text-align:center;}
.center-pane{grid-area:center;overflow-y:auto;padding:0;}
.list-head{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--border);background:var(--surface);position:sticky;top:0;z-index:5;}
.list-head h1{margin:0;font-size:19px;} .list-head .sub{color:var(--text-mute);font-size:12px;}
.searchbar{padding:10px 20px;border-bottom:1px solid var(--border);background:var(--surface);}
.searchbar input{width:100%;padding:9px 14px;border:1px solid var(--border);border-radius:999px;font-size:13px;outline:none;}
.searchbar input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-light);}
.mlist{display:flex;flex-direction:column;}
.mrow{display:grid;grid-template-columns:26px 180px 1fr 90px;gap:10px;align-items:center;padding:11px 20px;
  border-bottom:1px solid var(--border);cursor:pointer;background:var(--surface);}
.mrow:hover{background:var(--surface-2);} .mrow.unread{background:#faf9ff;}
.mrow.unread .who,.mrow.unread .subj{font-weight:700;color:var(--text);}
.mrow .star{cursor:pointer;color:var(--border);font-size:15px;} .mrow .star.on{color:var(--star);}
.mrow .who{color:var(--text-dim);font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.mrow .subj{font-size:13px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.mrow .subj .snip{color:var(--text-mute);font-weight:400;}
.mrow .when{color:var(--text-mute);font-size:12px;text-align:right;}
.mrow .dot{width:8px;height:8px;border-radius:50%;background:var(--accent);display:inline-block;}
.reading{padding:20px 24px;max-width:900px;}
.read-head{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:6px;}
.read-head h1{margin:0;font-size:21px;}
.read-actions{display:flex;gap:8px;flex-wrap:wrap;}
.email{border:1px solid var(--border);border-radius:10px;background:var(--surface);margin-bottom:12px;overflow:hidden;}
.email-head{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;}
.email-head .from{font-weight:700;} .email-head .addr{color:var(--text-mute);font-size:12px;}
.email-head .when{color:var(--text-mute);font-size:12px;}
.email-body{padding:14px 16px;white-space:pre-wrap;line-height:1.6;font-size:14px;color:var(--text-dim);}
.avatar{width:34px;height:34px;border-radius:50%;background:var(--accent-light);color:var(--accent-hover);
  display:inline-flex;align-items:center;justify-content:center;font-weight:700;margin-right:10px;}
.ai-panel{border:1px dashed var(--accent);background:var(--accent-light);border-radius:10px;padding:12px 16px;margin-bottom:12px;color:var(--accent-hover);font-size:13px;line-height:1.55;white-space:pre-wrap;}
.btn{padding:6px 12px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer;font-size:13px;}
.btn:hover{background:var(--surface-2);} .btn.primary{background:var(--accent);color:#fff;border-color:var(--accent);} .btn.primary:hover{background:var(--accent-hover);}
.compose{padding:20px 24px;max-width:760px;}
.compose .card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px;}
.compose label{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--text-mute);font-weight:600;margin:10px 0 4px;}
.compose input,.compose textarea{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:8px;font-size:14px;font-family:inherit;}
.compose textarea{min-height:200px;resize:vertical;}
.contacts-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;padding:20px 24px;}
.contact-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px;display:flex;align-items:center;gap:12px;}
.contact-card .nm{font-weight:600;} .contact-card .em{color:var(--text-mute);font-size:12px;}
.notice{margin:16px 24px;padding:12px 16px;background:var(--accent-light);border-left:4px solid var(--accent);color:var(--accent-hover);border-radius:8px;font-size:13px;}
.empty{padding:60px 24px;text-align:center;color:var(--text-mute);}
.login-wrap{height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#efeafd 0%,#ede9fe 100%);}
.login-card{background:#fff;padding:36px 40px;border-radius:14px;width:360px;box-shadow:0 20px 40px rgba(15,23,42,.08);}
.login-card h1{margin:0 0 4px;font-size:22px;} .login-card p{margin:0 0 20px;color:var(--text-mute);font-size:13px;}
.login-card input{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:8px;margin-bottom:10px;font-size:14px;}
.login-card button{width:100%;padding:10px;font-weight:600;} .login-card .error{color:var(--danger);font-size:12px;margin:6px 0;} .login-card .hint{font-size:11.5px;color:var(--text-mute);margin-top:10px;text-align:center;}
.right-pane{grid-area:right;background:var(--surface);border-left:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;}
.right-header{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;} .right-header h3{margin:0;font-size:14px;font-weight:700;} .right-header .tabs{display:flex;gap:6px;}
.chat-body{flex:1;overflow-y:auto;padding:14px 16px;display:flex;flex-direction:column;gap:12px;}
.msg{max-width:90%;padding:10px 14px;border-radius:12px;font-size:13px;line-height:1.55;overflow-wrap:anywhere;}
.msg.user{background:var(--accent);color:#fff;align-self:flex-end;border-bottom-right-radius:3px;white-space:pre-wrap;}
.msg.assistant{background:var(--surface-2);border:1px solid var(--border);color:var(--text);align-self:flex-start;border-bottom-left-radius:3px;}
.msg table{width:100%;table-layout:fixed;font-size:11.5px;border-collapse:collapse;border:1px solid var(--border);margin:6px 0;}
.msg th{background:var(--text);color:#fff;font-size:10.5px;} .msg th,.msg td{text-align:left;padding:5px 7px;border:1px solid var(--border);overflow-wrap:anywhere;}
.msg code{background:rgba(0,0,0,.06);padding:1px 4px;border-radius:3px;font-size:12px;}
.chat-input{border-top:1px solid var(--border);padding:10px;background:var(--surface);} .chat-input-row{display:flex;gap:8px;align-items:stretch;}
.chat-input-row input{flex:1;min-width:0;padding:10px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px;outline:none;}
.chat-input-row input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-light);}
.chat-send-btn{display:inline-flex;align-items:center;background:var(--accent);color:#fff;border:none;border-radius:8px;padding:0 16px;font-weight:600;font-size:13px;cursor:pointer;} .chat-send-btn:disabled{background:var(--text-mute);}
.chat-empty-hint{color:var(--text-mute);font-size:12.5px;line-height:1.5;text-align:center;padding:18px 14px;}
.sample-cards{padding:.4rem 1rem .8rem;background:var(--surface);border-top:1px solid var(--border);}
.sample-cards-label{display:inline-block;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.12em;color:var(--text-mute);margin-bottom:6px;}
.sample-card{display:flex;align-items:center;gap:8px;background:var(--bg);border:1px solid var(--border);padding:9px 12px;border-radius:10px;font-size:12.5px;cursor:pointer;color:var(--text-dim);width:100%;text-align:left;line-height:1.35;margin-bottom:6px;font-family:inherit;}
.sample-card::before{content:"💬";flex-shrink:0;} .sample-card:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-light);}
.thinking-indicator{display:flex;align-items:center;gap:8px;padding:6px 14px;font-size:12.5px;color:var(--text-mute);align-self:flex-start;}
.thinking-indicator .dot{width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 1.2s ease-in-out infinite;}
.spinner{display:inline-block;width:13px;height:13px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;vertical-align:middle;}
@keyframes spin{to{transform:rotate(360deg);}}
@keyframes pulse{0%,100%{opacity:.35;transform:scale(.85);}50%{opacity:1;transform:scale(1.1);}}
"""

FOLDER_ICONS = {"Inbox": "📥", "Starred": "⭐", "Sent": "📤", "Drafts": "📝",
                "Archive": "🗄️", "Spam": "🚫", "Trash": "🗑️"}
SAMPLE_QUESTIONS = ["What needs my reply today?", "Any overdue invoices?", "Summarise my unread mail."]


def topbar(env, user_email):
    right = Div(
        Button(NotStr("&laquo; Chat"), id="copilot-topbar-toggle", cls="btn", onclick="toggleCopilot()") if user_email else None,
        Span(env, cls="env-pill"),
        Span(f"{db.ACCOUNT_NAME} <{db.ACCOUNT_EMAIL}>" if user_email else "", cls="who"),
        A("Logout", href="/logout", cls="btn") if user_email else None, cls="actions")
    return Div(Div(Span(cls="brand-dot"), Span("Fast", style="font-weight:800;"),
                   Span("Mail", style="color:var(--accent);font-weight:700;letter-spacing:.5px;"), cls="brand"),
               right, cls="topbar")


def left_pane(active, counts):
    items = []
    for f in ["Inbox", "Starred", "Sent", "Drafts", "Archive", "Spam", "Trash"]:
        c = counts.get(f, {"total": 0, "unread": 0})
        badge = (Span(str(c["unread"]), cls="badge") if c["unread"]
                 else (Span(str(c["total"]), cls="cnt") if c["total"] else None))
        items.append(A(Span(FOLDER_ICONS[f], cls="nav-icon"), Span(f), badge,
                       href=f"/folder/{f}", cls=f"nav-item {'active' if active == f else ''}"))
    extra = Div(H4("MORE"),
                A(Span("👥", cls="nav-icon"), Span("Contacts"), href="/contacts",
                  cls=f"nav-item {'active' if active == 'contacts' else ''}"),
                A(Span("🤖", cls="nav-icon"), Span("AI Assistant"), href="/ai",
                  cls=f"nav-item {'active' if active == 'ai' else ''}"),
                A(Span("📖", cls="nav-icon"), Span("User Guide"), href="/guide",
                  cls=f"nav-item {'active' if active == 'guide' else ''}"),
                cls="nav-section")
    return Div(A("✏️  Compose", href="/compose", cls="compose-btn"),
               Div(H4("FOLDERS"), *items, cls="nav-section"), extra, cls="left-pane")


def _sample_cards():
    cards = [Button(Span(q), cls="sample-card", onclick=f"fillChat({q!r});sendMessage(null);", title=q) for q in SAMPLE_QUESTIONS]
    return Div(Div(Span("Try asking:", cls="sample-cards-label")), Div(*cards), cls="sample-cards")


def right_pane_chat(thread_id):
    return Div(
        Div(H3("AI Assistant"),
            Div(Button("New", cls="btn", hx_get="/chat/new", hx_target="#chat-body", hx_swap="innerHTML"),
                Button(NotStr("&laquo;"), id="copilot-exp-btn", cls="copilot-exp", onclick="toggleExpand()"),
                Button(NotStr("&rsaquo;"), cls="copilot-min", onclick="toggleCopilot()"), cls="tabs"),
            cls="right-header"),
        Div(Div(P("Ask about your mailbox — or use /unread /find /help. Open a message to summarise or draft a reply.",
                  cls="chat-empty-hint"), id="chat-body", cls="chat-body"),
            Form(Input(type="hidden", name="thread_id", value=thread_id, id="thread-id"),
                 Div(Input(type="text", name="message", id="chat-input",
                           placeholder="Ask about your mail or /unread /help …", autocomplete="off"),
                     Button("Send", type="submit", cls="chat-send-btn", id="chat-send-btn"), cls="chat-input-row"),
                 onsubmit="return streamChat(event)", cls="chat-input"),
            _sample_cards(),
            style="display:flex;flex-direction:column;flex:1;overflow:hidden;"),
        cls="right-pane")


def page(active, env, user_email, thread_id, counts, *content, right_override=None):
    right = right_override if right_override is not None else right_pane_chat(thread_id)
    return (Title("FastMail"),
            Link(rel="icon", type="image/svg+xml", href="/static/favicon.svg"),
            Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
            Style(LAYOUT_CSS),
            Div(topbar(env, user_email), left_pane(active, counts), Div(*content, cls="center-pane"), right,
                Div(NotStr("&lsaquo; AI Assistant"), id="copilot-reopen", onclick="toggleCopilot()"), cls="app"),
            Script(LAYOUT_JS))


LAYOUT_JS = """
function _sync(){var app=document.querySelector('.app');if(!app)return;
  var ex=app.classList.contains('right-expanded'),col=app.classList.contains('right-collapsed');
  var eb=document.getElementById('copilot-exp-btn');if(eb){eb.innerHTML=ex?'\\u00BB':'\\u00AB';}
  var tb=document.getElementById('copilot-topbar-toggle');if(tb){tb.innerHTML=col?'\\u00AB Chat':'Chat \\u203A';}}
function toggleCopilot(){var app=document.querySelector('.app');if(!app)return;app.classList.toggle('right-collapsed');
  if(app.classList.contains('right-collapsed'))app.classList.remove('right-expanded');
  try{localStorage.setItem('fmCollapsed',app.classList.contains('right-collapsed')?'1':'0');}catch(e){}_sync();}
function toggleExpand(){var app=document.querySelector('.app');if(!app)return;app.classList.remove('right-collapsed');app.classList.toggle('right-expanded');
  try{localStorage.setItem('fmExpanded',app.classList.contains('right-expanded')?'1':'0');localStorage.setItem('fmCollapsed','0');}catch(e){}_sync();}
(function(){try{var app=document.querySelector('.app');if(!app)return;
  if(localStorage.getItem('fmCollapsed')==='1')app.classList.add('right-collapsed');
  else if(localStorage.getItem('fmExpanded')==='1')app.classList.add('right-expanded');}catch(e){}})();
document.addEventListener('DOMContentLoaded',_sync);
function openMsg(id){window.location='/message/'+id;}
function fillChat(t){var el=document.getElementById('chat-input');if(el){el.value=t;el.focus();}}
function sendMessage(ev){return streamChat(ev);}
var _streaming=false,_thinker=null;
function _esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function _md(t){try{return marked.parse(t);}catch(e){return _esc(t);}}
function _scroll(){var cb=document.getElementById('chat-body');if(cb)cb.scrollTop=cb.scrollHeight;}
function addBubble(role,html){var cb=document.getElementById('chat-body');if(!cb)return null;
  var h=cb.querySelector('.chat-empty-hint');if(h)h.style.display='none';
  var d=document.createElement('div');d.className='msg '+role;d.innerHTML=html||'';cb.appendChild(d);_scroll();return d;}
function showThinking(){var cb=document.getElementById('chat-body');if(!cb)return;
  _thinker={el:document.createElement('div')};_thinker.el.className='thinking-indicator';
  _thinker.el.innerHTML='<span class="dot"></span> Thinking…';cb.appendChild(_thinker.el);_scroll();}
function hideThinking(){if(_thinker){if(_thinker.el.parentNode)_thinker.el.parentNode.removeChild(_thinker.el);_thinker=null;}}
async function streamChat(ev){if(ev&&ev.preventDefault)ev.preventDefault();if(_streaming)return false;
  var input=document.getElementById('chat-input');var msg=input?input.value.trim():'';if(!msg)return false;
  _streaming=true;var btn=document.getElementById('chat-send-btn');if(btn)btn.disabled=true;
  addBubble('user',_esc(msg));input.value='';
  var tid=(document.getElementById('thread-id')||{}).value||'';var bubble=null,acc='';showThinking();
  try{var resp=await fetch('/chat/stream',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({message:msg,thread_id:tid})});
    if(!resp.ok){hideThinking();addBubble('assistant','Error: '+resp.status);_streaming=false;if(btn)btn.disabled=false;return false;}
    var reader=resp.body.getReader(),dec=new TextDecoder(),buf='';
    while(true){var r=await reader.read();if(r.done)break;buf+=dec.decode(r.value,{stream:true});
      var idx;while((idx=buf.indexOf('\\n\\n'))!==-1){var raw=buf.slice(0,idx);buf=buf.slice(idx+2);
        if(raw.indexOf('data: ')!==0)continue;var p={};try{p=JSON.parse(raw.slice(6));}catch(e){}
        if(p.token){if(acc===''){hideThinking();bubble=addBubble('assistant','');}acc+=p.token;bubble.innerHTML=_md(acc);_scroll();}
        else if(p.error){hideThinking();addBubble('assistant','⚠ '+p.error);}}}
  }catch(e){hideThinking();addBubble('assistant','⚠ '+e);}
  hideThinking();_streaming=false;if(btn)btn.disabled=false;return false;}
"""
