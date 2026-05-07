import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import './index.css'

// VRED WebEngine VR pointer shim + event diagnostics overlay
;(function installVRPointerShim() {
  // ---------- Debug overlay ----------
  // const dbg = document.createElement('div')
  // dbg.style.cssText = [
  //   'position:fixed', 'bottom:6px', 'right:6px', 'z-index:2147483647',
  //   'background:rgba(0,0,0,0.88)', 'color:#39C5BB', 'font:11px/1.6 monospace',
  //   'padding:8px 12px', 'border-radius:8px', 'border:1px solid #39C5BB44',
  //   'pointer-events:none', 'max-width:340px', 'white-space:pre',
  // ].join(';')
  // const appendLog = (() => {
  //   const lines = []
  //   return (msg) => {
  //     const ts = new Date().toISOString().slice(11, 23)
  //     lines.unshift(`${ts} ${msg}`)
  //     if (lines.length > 10) lines.pop()
  //     dbg.textContent = lines.join('\n')
  //   }
  // })()
  // const attachDbg = () => { if (document.body) document.body.appendChild(dbg) }
  // if (document.body) attachDbg()
  // else document.addEventListener('DOMContentLoaded', attachDbg, { once: true })

  // ---------- Watch all candidate events ----------
  const WATCH = ['pointerdown','pointerup','mousedown','mouseup','click']
  WATCH.forEach(type => {
    document.addEventListener(type, (e) => {
      const tag = e.target?.tagName ?? '?'
      const pt  = e.pointerType !== undefined ? `pt=${e.pointerType}` : ''
      const pos = `(${Math.round(e.clientX)},${Math.round(e.clientY)})`
      appendLog(`[${type}] <${tag}> ${pt} ${pos}`)
    }, { capture: true, passive: true })
  })

  // ---------- Shim: promote pointerdown -> click (mousedown removed to prevent double-fire) ----------
  const INTERACTIVE = 'button, a, input, select, textarea, [role="button"], [tabindex]'
  const fireClick = (() => {
    let lastFired = 0
    return (e, src) => {
      const now = Date.now()
      if (now - lastFired < 300) {
        appendLog(`[shim-${src}] debounced (${now - lastFired}ms)`)
        return
      }
      lastFired = now
      const target = e.target instanceof Element ? e.target.closest(INTERACTIVE) : null
      if (!target) {
        appendLog(`[shim-${src}] no interactive target @ <${e.target?.tagName ?? '?'}>`)
        return
      }
      appendLog(`[shim-${src}] -> click on <${target.tagName}> "${(target.textContent || '').trim().slice(0, 20)}"`)
      target.dispatchEvent(new MouseEvent('click', {
        bubbles: true, cancelable: true, view: window,
        clientX: e.clientX, clientY: e.clientY,
      }))
    }
  })()

  document.addEventListener('pointerdown', (e) => fireClick(e, 'PD'), { capture: true })
})()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>,
)
