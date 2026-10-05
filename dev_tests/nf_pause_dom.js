(() => {
  const v = document.querySelector('video');
  const desc = n => n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') +
    (typeof n.className === 'string' && n.className.trim() ? '.' + n.className.trim().split(/\s+/).join('.') : '') +
    (n.getAttribute('data-uia') ? '[data-uia="' + n.getAttribute('data-uia') + '"]' : '') +
    ' ' + Math.round(n.getBoundingClientRect().width) + 'x' + Math.round(n.getBoundingClientRect().height);
  const labels = [...document.querySelectorAll('body *')].filter(e =>
    e.children.length === 0 && /^(Werbung|Anzeige|Ad)$/i.test((e.textContent || '').trim()));
  return {
    t: v ? Math.round(v.currentTime) : null, paused: v ? v.paused : null,
    labels: labels.map(e => { const c = []; for (let n = e, i = 0; n && n !== document.body && i < 16; i++, n = n.parentElement) c.push(desc(n)); return c; }),
    uias: [...new Set([...document.querySelectorAll('[data-uia]')].map(e => e.getAttribute('data-uia')))].filter(u => /ad|pause|interrupt|sponsor|promo/i.test(u)),
  };
})()
