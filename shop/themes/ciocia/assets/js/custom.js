/*
 * Tablet (768-991 px): the source puts heart and account right of the cart, not in the
 * category row. Move the nodes instead of rendering them twice: Classic's responsive
 * script needs a single #_desktop_user_info, and DOM order stays equal to visual order.
 * Runs at once (this file loads after the header) to keep the icons from jumping late.
 */
(function () {
  var tablet = window.matchMedia('(min-width: 768px) and (max-width: 991px)');

  function placeHeaderIcons() {
    var actions = document.querySelector('#header .ciocia-header-actions');
    var categoryRow = document.querySelector('#header .ciocia-desktop-navigation .header-top-right');
    var icons = [
      document.querySelector('#header .ciocia-header-wishlist'),
      document.querySelector('#header .ciocia-header-account')
    ].filter(Boolean);
    if (!actions || !categoryRow || !icons.length) return false;

    var target = tablet.matches ? actions : categoryRow;
    if (icons[0].parentElement === target) return true;
    // Moving a node drops its focus; give it back when the viewport changes mid-tab.
    var focused = icons.find(function (icon) { return icon.contains(document.activeElement); }) && document.activeElement;
    target.append.apply(target, icons);
    if (focused) focused.focus();
    return true;
  }

  if (!placeHeaderIcons()) document.addEventListener('DOMContentLoaded', placeHeaderIcons);
  tablet.addEventListener('change', placeHeaderIcons);
})();

/*
 * Desktop (992 px+): the header sticks to the top (CSS). After 100 px of scroll, .is-compact folds
 * away the top bar and the category row, leaving logo, search and cart; at 60 px or less they come
 * back. The gap between the two values stops flicker on slow scroll.
 * CSS cannot animate to or from height: auto, so this script measures each folding row and passes
 * its height as --ciocia-row-height. It also sets on <html>:
 *   --ciocia-header-collapsed: how much shorter the compact header is. The margin under the header
 *     grows by this much while the rows shrink, so the page below does not move.
 *   --ciocia-header-height: the header's height now, for scroll-margin on focused fields.
 *   --ciocia-header-compact-height: for other sticky elements, such as the checkout summary.
 */
(function () {
  var header = document.getElementById('header');
  if (!header) return;
  var root = document.documentElement;
  var desktop = window.matchMedia('(min-width: 992px)');
  var rows = Array.from(header.querySelectorAll('.header-banner, .ciocia-topbar, .ciocia-desktop-navigation'));
  var COLLAPSE_AFTER = 100;
  var EXPAND_AT = 60;
  var fullHeight = 0;
  var compactHeight = 0;
  var scheduled = false;

  function setCompact(compact) {
    header.classList.toggle('is-compact', compact);
    if (desktop.matches) root.style.setProperty('--ciocia-header-height', (compact ? compactHeight : fullHeight) + 'px');
  }

  function measure() {
    if (!desktop.matches) {
      rows.forEach(function (row) { row.style.removeProperty('--ciocia-row-height'); });
      ['--ciocia-header-height', '--ciocia-header-compact-height', '--ciocia-header-collapsed']
        .forEach(function (name) { root.style.removeProperty(name); });
      return;
    }
    // .is-measuring turns transitions off and gives the rows their natural height. Classes change
    // back and forth within one task, so the browser lays the states out but never paints them.
    var compact = header.classList.contains('is-compact');
    header.classList.add('is-measuring');
    // getBoundingClientRect, not offsetHeight: heights such as 25.06 px must not be rounded.
    function height(el) { return el.getBoundingClientRect().height; }
    header.classList.remove('is-compact');
    fullHeight = height(header);
    var rowHeights = rows.map(height);
    header.classList.add('is-compact');
    compactHeight = height(header);
    header.classList.toggle('is-compact', compact);

    rows.forEach(function (row, i) { row.style.setProperty('--ciocia-row-height', rowHeights[i] + 'px'); });
    root.style.setProperty('--ciocia-header-compact-height', compactHeight + 'px');
    root.style.setProperty('--ciocia-header-collapsed', (fullHeight - compactHeight) + 'px');
    setCompact(compact);
    // Apply the new values while transitions are still off, so nothing animates from the old ones.
    height(header);
    header.classList.remove('is-measuring');
    // Settle the normal state now too. Otherwise the next fold would start from the measuring
    // state, where rows have height: auto, which cannot animate: rows would jump, the margin not.
    height(header);
  }

  function update() {
    scheduled = false;
    var y = window.scrollY;
    if (!desktop.matches || y <= EXPAND_AT) {
      setCompact(false);
    } else if (y > COLLAPSE_AFTER && !rows.some(function (row) { return row.contains(document.activeElement); })) {
      // Do not hide a row while keyboard focus is inside it.
      setCompact(true);
    }
  }

  function scheduleUpdate() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(update);
  }

  window.addEventListener('scroll', scheduleUpdate, { passive: true });
  // Focus leaving the top bar or the category row may let the header collapse now.
  header.addEventListener('focusout', scheduleUpdate);
  desktop.addEventListener('change', function () {
    measure();
    update();
  });
  // Watch the row contents, not the header: the header itself changes size while it animates.
  // Fires once at start and again when fonts load, the menu wraps or the width changes.
  var observer = new ResizeObserver(measure);
  header.querySelectorAll('.header-banner > *, .ciocia-topbar > .container, .ciocia-header-layout, .ciocia-desktop-navigation > .container')
    .forEach(function (el) { observer.observe(el); });
  measure();
  update();
})();

/* Keep Classic's responsive module relocation; own the mobile drawer interaction. */
document.addEventListener('DOMContentLoaded', function () {
  var toggle = document.getElementById('menu-icon');
  var menu = document.getElementById('mobile_top_menu_wrapper');
  var backdrop = document.querySelector('.ciocia-menu-backdrop');
  var closeButton = menu && menu.querySelector('.ciocia-menu-close');
  // Only bind to the ciocia header markup; leave any other header untouched.
  if (!toggle || !menu || !backdrop || !closeButton) return;

  function updateExpandedState() {
    toggle.setAttribute('aria-expanded', String(getComputedStyle(menu).display !== 'none'));
  }

  new MutationObserver(updateExpandedState).observe(menu, {
    attributes: true,
    attributeFilter: ['style', 'class']
  });
  updateExpandedState();

  var previousOverflow;
  var inertElements = [];
  function setDrawer(open) {
    if (open === (toggle.getAttribute('aria-expanded') === 'true')) return;
    if (open) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      inertElements = Array.from(document.querySelectorAll('#wrapper, #footer')).filter(function (el) { return !el.inert; });
      inertElements.forEach(function (el) { el.inert = true; });
      menu.setAttribute('role', 'dialog');
      menu.setAttribute('aria-modal', 'true');
      menu.setAttribute('aria-labelledby', 'ciocia-menu-title');
    } else {
      document.body.style.overflow = previousOverflow;
      inertElements.forEach(function (el) { el.inert = false; });
      menu.removeAttribute('role');
      menu.removeAttribute('aria-modal');
      menu.removeAttribute('aria-labelledby');
    }
    menu.style.display = open ? 'flex' : 'none';
    backdrop.hidden = !open;
    updateExpandedState();
    if (open) closeButton.focus();
    else toggle.focus();
  }
  // Capture before Classic's delegated click handler, which hides page content.
  toggle.addEventListener('click', function (event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    setDrawer(toggle.getAttribute('aria-expanded') !== 'true');
  }, true);
  closeButton.addEventListener('click', function () { setDrawer(false); });
  backdrop.addEventListener('click', function () { setDrawer(false); });
  menu.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && event.target === closeButton) {
      event.preventDefault();
      setDrawer(false);
      return;
    }
    if (event.key !== 'Tab') return;
    var focusable = Array.from(menu.querySelectorAll('a, button, input, select')).filter(function (el) {
      return el.getClientRects().length && !el.closest('[hidden]');
    });
    if (event.shiftKey && document.activeElement === focusable[0]) {
      event.preventDefault();
      focusable[focusable.length - 1].focus();
    } else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
      event.preventDefault();
      focusable[0].focus();
    }
  });
  window.matchMedia('(min-width: 768px)').addEventListener('change', function (event) {
    if (event.matches) setDrawer(false);
  });

  var currencyToggle = document.getElementById('ciocia-currency-toggle');
  if (currencyToggle) {
    var currencyMenu = currencyToggle.parentElement.querySelector('.dropdown-menu');
    function currencyLinks() {
      return Array.from(currencyMenu.querySelectorAll('a'));
    }
    function closeCurrency() {
      if (currencyToggle.getAttribute('aria-expanded') === 'true') currencyToggle.click();
    }
    currencyToggle.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        event.stopPropagation();
        if (currencyToggle.getAttribute('aria-expanded') !== 'true') currencyToggle.click();
        var links = currencyLinks();
        if (links.length) links[event.key === 'ArrowDown' ? 0 : links.length - 1].focus();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        closeCurrency();
      }
    });
    currencyMenu.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        closeCurrency();
        currencyToggle.focus();
      } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        event.stopPropagation();
        var links = currencyLinks();
        var index = links.indexOf(document.activeElement);
        links[(index + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length].focus();
      }
    });
    currencyToggle.parentElement.addEventListener('focusout', function (event) {
      if (!currencyToggle.parentElement.contains(event.relatedTarget)) closeCurrency();
    });
  }

  // Keep category navigation usable without a mouse, at every menu depth.
  var categoryMenu = document.getElementById('top-menu');
  if (!categoryMenu) return;
  var items = Array.from(categoryMenu.querySelectorAll('.ciocia-has-submenu'));

  function controls(item) {
    return {
      button: Array.from(item.children).find(function (el) { return el.classList.contains('ciocia-submenu-toggle'); }),
      panel: Array.from(item.children).find(function (el) { return el.classList.contains('ciocia-submenu'); })
    };
  }

  function setOpen(item, open) {
    var parts = controls(item);
    if (!parts.button || !parts.panel) return;
    parts.button.setAttribute('aria-expanded', String(open));
    parts.panel.hidden = !open;
    if (!open) {
      item.querySelectorAll('.ciocia-has-submenu').forEach(function (child) { setOpen(child, false); });
    }
  }

  items.forEach(function (item) {
    var parts = controls(item);
    if (!parts.button || !parts.panel) return;
    parts.button.addEventListener('click', function () {
      setOpen(item, parts.button.getAttribute('aria-expanded') !== 'true');
    });
    item.addEventListener('mouseenter', function () {
      if (window.matchMedia('(min-width: 768px)').matches) setOpen(item, true);
    });
    item.addEventListener('mouseleave', function () {
      if (!item.contains(document.activeElement) && window.matchMedia('(min-width: 768px)').matches) setOpen(item, false);
    });
    // Desktop only: in the drawer, closing on press shifts the layout and the tap misses its target.
    item.addEventListener('focusout', function (event) {
      if (!item.contains(event.relatedTarget) && window.matchMedia('(min-width: 768px)').matches) setOpen(item, false);
    });
  });

  categoryMenu.addEventListener('keydown', function (event) {
    var item = event.target.closest('.ciocia-has-submenu');
    if (event.key === 'Escape' && item) {
      // Close the nearest open submenu and return focus to its own toggle.
      while (item && controls(item).panel.hidden) {
        item = item.parentElement.closest('.ciocia-has-submenu');
      }
      if (item) {
        event.preventDefault();
        setOpen(item, false);
        controls(item).button.focus();
      }
      return;
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    var panel;
    if (item && event.target.parentElement === item) {
      setOpen(item, true);
      panel = controls(item).panel;
    } else {
      panel = event.target.closest('.ciocia-submenu');
    }
    if (!panel) return;
    var links = Array.from(panel.querySelectorAll('a, button')).filter(function (el) {
      return !el.closest('[hidden]') && el.getClientRects().length;
    });
    if (!links.length) return;
    event.preventDefault();
    var index = links.indexOf(event.target);
    var next = index < 0 ? (event.key === 'ArrowDown' ? 0 : links.length - 1) :
      (index + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
    links[next].focus();
  });

  // Escape also closes the complete mobile menu when no submenu is open.
  menu.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !categoryMenu.querySelector('.ciocia-submenu-toggle[aria-expanded="true"]')) {
      if (!event.defaultPrevented && toggle.getAttribute('aria-expanded') === 'true') {
        event.preventDefault();
        toggle.click();
        toggle.focus();
      }
    }
  });
  window.matchMedia('(min-width: 768px)').addEventListener('change', function () {
    items.forEach(function (item) { setOpen(item, false); });
  });
});

/*
 * Cookie notice (templates/_partials/cookie-notice.tpl). The choice is saved in localStorage, so the
 * panel shows only until the visitor picks an option; after that only the "Cookies" tab is shown.
 * Runs at once: this file loads after the footer, so the panel appears without a late jump.
 */
(function () {
  var STORAGE_KEY = 'ciocia_cookie_consent';
  var notice = document.getElementById('ciocia-cookie-notice');
  var reopen = document.getElementById('ciocia-cookie-reopen');
  if (!notice || !reopen) return;
  var details = document.getElementById('ciocia-cookie-details');
  var customize = notice.querySelector('[data-cookie-customize]');
  var analytics = notice.querySelector('[data-cookie-analytics]');
  var ads = notice.querySelector('[data-cookie-ads]');

  // Storage can be blocked (private mode, site data off); then the panel simply shows again.
  function readChoice() {
    try {
      return JSON.parse(window.localStorage.getItem(STORAGE_KEY));
    } catch {
      return null;
    }
  }
  function saveChoice(choice) {
    choice.date = new Date().toISOString();
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(choice));
    } catch { /* keep working for this page view */ }
  }

  // Leave room under the page for the fixed panel or tab, so they never hide its last content.
  function reserveSpace() {
    var visible = notice.hidden ? reopen : notice;
    document.body.style.paddingBottom = visible.offsetHeight + 'px';
  }

  function setDetails(open) {
    details.hidden = !open;
    customize.setAttribute('aria-expanded', String(open));
    reserveSpace();
  }

  // As on the source: the first visit shows the short panel, the "Cookies" tab opens it with the
  // options already expanded, set to the saved choice.
  function showNotice(withDetails) {
    var choice = readChoice() || {};
    analytics.checked = Boolean(choice.analytics);
    ads.checked = Boolean(choice.ads);
    setDetails(withDetails);
    notice.hidden = false;
    reopen.hidden = true;
    reserveSpace();
  }

  function closeNotice(choice) {
    if (choice) saveChoice(choice);
    // Only a keyboard user (focus ring shown in the panel) gets focus moved to the "Cookies" tab;
    // after a mouse click the tab would otherwise show a focus ring nobody asked for.
    var keyboardFocus = Boolean(notice.querySelector(':focus-visible'));
    notice.hidden = true;
    reopen.hidden = false;
    reserveSpace();
    // The focused button disappears with the panel; hand focus to the control that brings it back.
    if (keyboardFocus) reopen.focus();
  }

  notice.querySelector('[data-cookie-accept]').addEventListener('click', function () {
    closeNotice({ necessary: true, analytics: true, ads: true });
  });
  notice.querySelector('[data-cookie-necessary]').addEventListener('click', function () {
    closeNotice({ necessary: true, analytics: false, ads: false });
  });
  notice.querySelector('[data-cookie-save]').addEventListener('click', function () {
    closeNotice({ necessary: true, analytics: analytics.checked, ads: ads.checked });
  });
  customize.addEventListener('click', function () {
    setDetails(details.hidden);
  });
  reopen.addEventListener('click', function () {
    showNotice(true);
    notice.querySelector('[data-cookie-accept]').focus();
  });
  // Escape closes a reopened panel without changing the saved choice; the first choice must be made.
  notice.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && readChoice()) closeNotice(null);
  });
  window.addEventListener('resize', reserveSpace);

  if (readChoice()) closeNotice(null);
  else showNotice(false);
})();
