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
 * Folded rows are visibility: hidden, so Tab skips them: once the header is compact, the top bar and
 * the category menu are out of reach of the keyboard until the page is scrolled back up (Home key).
 * The source shop behaves the same, and the search and cart stay reachable. A row with focus inside
 * it does not fold.
 * CSS cannot animate to or from height: auto, so this script measures each folding row and passes
 * its height as --ciocia-row-height. It also sets on <html>:
 *   --ciocia-header-collapsed: how much shorter the compact header is. The margin under the header
 *     grows by this much while the rows shrink, so the page below does not move.
 *   --ciocia-header-height: the header's height now, for scroll-margin on focused fields.
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
      ['--ciocia-header-height', '--ciocia-header-collapsed']
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

/*
 * Cart preview (modules/ps_shoppingcart/ps_shoppingcart.tpl, from 768 px). CSS opens it on hover and
 * focus; this adds the Escape key (WCAG 1.4.13: dismissible). Escape sets .is-dismissed on .blockcart,
 * and the panel stays closed until the pointer and the focus have both left the cart.
 * Listeners sit on the document, not on the cart: after an AJAX refresh ps_shoppingcart replaces the
 * whole .blockcart element, which would drop listeners attached to it.
 */
(function () {
  var DISMISSED = 'is-dismissed';
  var wide = window.matchMedia('(min-width: 768px)');

  function cartOf(node) {
    return node instanceof Element ? node.closest('.blockcart') : null;
  }

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'Escape' || !wide.matches) return;
    document.querySelectorAll('.blockcart').forEach(function (cart) {
      if (cart.classList.contains(DISMISSED) || !(cart.matches(':hover') || cart.matches(':focus-within'))) return;
      // Focus inside the panel would be lost when it hides; hand it back to the cart link.
      var link = cart.querySelector('.ciocia-cart-link');
      if (link && cart.contains(document.activeElement) && document.activeElement !== link) link.focus();
      cart.classList.add(DISMISSED);
    });
  });

  document.addEventListener('mouseout', function (event) {
    var cart = cartOf(event.target);
    if (cart && !cart.contains(event.relatedTarget) && !cart.matches(':focus-within')) cart.classList.remove(DISMISSED);
  });

  document.addEventListener('focusout', function (event) {
    var cart = cartOf(event.target);
    if (cart && !cart.contains(event.relatedTarget) && !cart.matches(':hover')) cart.classList.remove(DISMISSED);
  });
})();

/*
 * Password fields (templates/_partials/form-fields.tpl): the eye button shows or hides the password.
 * Delegated from the document, because checkout replaces its forms after AJAX updates.
 */
document.addEventListener('click', function (event) {
  var button = event.target.closest('[data-action="ciocia-show-password"]');
  if (!button) return;
  // Not by id: checkout has a login form and a registration form, both with "field-password".
  var input = button.closest('.input-group').querySelector('input.js-visible-password');
  if (!input) return;
  var show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  button.setAttribute('aria-label', show ? button.dataset.labelHide : button.dataset.labelShow);
  button.querySelector('.material-icons').textContent = show ? 'visibility_off' : 'visibility';
});

/*
 * Checkout steps bar (templates/checkout/checkout.tpl, issue #44). Built from the step sections,
 * whose classes Classic's checkout script sets: -current, -complete, -unreachable, and -clickable on
 * the current step and those before it. Any class change rebuilds the bar, so it follows Classic
 * however the step changed. .ciocia-has-steps-bar on <body> then shows only the current step.
 * A completed step is a link that clicks that step's (now hidden) title, so Classic's own handler
 * switches the step. Focus then moves to the new step's heading, so the next Tab lands in its form.
 * Runs at once: this file loads after the checkout, so the bar shows without a late jump.
 */
(function () {
  var nav = document.querySelector('.ciocia-steps');
  if (!nav) return;
  var list = nav.querySelector('.ciocia-steps__list');
  var sections = Array.from(document.querySelectorAll('#checkout section.checkout-step'));
  if (!sections.length) return;

  // Step name without Classic's number, tick and "Edytuj".
  function stepName(section) {
    var title = section.querySelector('.step-title').cloneNode(true);
    title.querySelectorAll('.step-number, .step-edit, .material-icons').forEach(function (el) { el.remove(); });
    return title.textContent.trim();
  }

  function openStep(section) {
    var title = section.querySelector('.step-title');
    title.click();
    title.setAttribute('tabindex', '-1');
    title.focus();
  }

  function stepState(section, index, current) {
    var classes = section.classList;
    if (index === current) return 'current';
    // Classic adds -clickable once its script starts; until then, being before the current step means the same.
    var isComplete = classes.contains('-complete') && !classes.contains('-unreachable') &&
      (classes.contains('-clickable') || index < current);
    return isComplete ? 'complete' : 'todo';
  }

  function createItem(section, index, state) {
    var isCurrent = state === 'current';
    var isComplete = state === 'complete';
    var item = document.createElement('li');
    item.className = 'ciocia-steps__item is-' + state;
    var step = document.createElement(isComplete ? 'a' : 'span');
    step.className = 'ciocia-steps__step';
    var number = document.createElement('span');
    number.className = 'ciocia-steps__number';
    number.textContent = index + 1;
    var name = document.createElement('span');
    name.className = 'ciocia-steps__label';
    name.textContent = stepName(section);
    step.append(number, name);

    if (isCurrent) step.setAttribute('aria-current', 'step');
    if (isComplete) {
      step.href = '#' + section.id;
      var status = document.createElement('span');
      status.className = 'sr-only';
      status.textContent = ', ' + nav.dataset.completeLabel;
      step.append(status);
      step.addEventListener('click', function (event) {
        event.preventDefault();
        openStep(section);
      });
    }
    item.append(step);
    return item;
  }

  // Classic also changes classes that do not change the bar (-clickable at start, for one). Rebuilding
  // then would only throw away the link that has keyboard focus, so the bar changes with the states only.
  var shownStates = '';
  function render() {
    var current = sections.findIndex(function (section) { return section.classList.contains('-current'); });
    var states = sections.map(function (section, index) { return stepState(section, index, current); });
    if (states.join() === shownStates) return;
    shownStates = states.join();
    list.replaceChildren.apply(list, sections.map(function (section, index) {
      return createItem(section, index, states[index]);
    }));
    renderCompact(current);
  }

  // Phones: "1 / 4" in a ring filled to the same share, the current step and the next one.
  function renderCompact(current) {
    if (current < 0) return;
    var next = sections[current + 1];
    nav.querySelector('[data-steps-position]').textContent = current + 1;
    nav.querySelector('[data-steps-count]').textContent = sections.length;
    nav.querySelector('.ciocia-steps__ring').style.setProperty('--ciocia-steps-progress', (current + 1) / sections.length);
    nav.querySelector('[data-steps-current]').textContent = stepName(sections[current]);
    nav.querySelector('[data-steps-next]').textContent = next ? stepName(next) : '';
    nav.querySelector('[data-steps-next-row]').hidden = !next;
  }

  /*
   * "Wróć do ..." from step 2 on, left of the step's main button ("Dalej", "Złóż zamówienie"). Both go in
   * one row, put where the main button was, so it stays in its form and Classic's submit still works.
   * On the payment step the row takes the whole #payment-confirmation: Classic handles and disables
   * every button inside it, so the back button must stay outside.
   * The label comes from data-back-<previous step id> in checkout.tpl.
   */
  function addBackButton(section, index) {
    var previous = sections[index - 1];
    var label = previous && nav.getAttribute('data-back-' + previous.id);
    if (!label) return;
    section.querySelectorAll('button.continue, #payment-confirmation').forEach(function (main) {
      var row = document.createElement('div');
      row.className = 'ciocia-step-actions';
      var back = document.createElement('button');
      back.type = 'button';
      back.className = 'btn btn-outline-primary ciocia-step-back';
      back.textContent = label;
      back.addEventListener('click', function () { openStep(previous); });
      main.before(row);
      row.append(back, main);
    });
  }

  var observer = new MutationObserver(render);
  sections.forEach(function (section, index) {
    observer.observe(section, { attributes: true, attributeFilter: ['class'] });
    addBackButton(section, index);
  });
  render();
  nav.hidden = false;
  document.body.classList.add('ciocia-has-steps-bar');
})();

/*
 * Cart quantity buttons (templates/checkout/_partials/cart-detailed-product-line.tpl, issue #44).
 * Classic's TouchSpin draws "+" and "−" as buttons holding only an icon, on load and after every cart
 * change. Each gets a name from data-label-up / data-label-down on its field ("Zwiększ ilość: <product>"),
 * so screen readers can tell them apart. Watches the cart list, which Classic rebuilds after a change.
 */
(function () {
  var list = document.querySelector('#cart .cart-grid-body');
  if (!list) return;

  function nameButtons() {
    list.querySelectorAll('.bootstrap-touchspin').forEach(function (spin) {
      var field = spin.querySelector('input[name="product-quantity-spin"]');
      if (!field) return;
      [['.bootstrap-touchspin-up', 'labelUp'], ['.bootstrap-touchspin-down', 'labelDown']].forEach(function (pair) {
        var button = spin.querySelector(pair[0]);
        if (button && !button.hasAttribute('aria-label')) button.setAttribute('aria-label', field.dataset[pair[1]]);
      });
    });
  }

  new MutationObserver(nameButtons).observe(list, { childList: true, subtree: true });
  nameButtons();
})();

/*
 * Checkout tabs "Zamówienie jako gość" / "Zaloguj się" (steps/personal-information.tpl, issue #44).
 * Bootstrap moves only the "active" class between them; aria-selected follows it here, so screen
 * readers announce which tab is open.
 */
(function () {
  var tabs = document.querySelectorAll('.ciocia-tabs [role="tab"]');
  if (!tabs.length) return;
  var observer = new MutationObserver(function () {
    tabs.forEach(function (tab) {
      tab.setAttribute('aria-selected', String(tab.classList.contains('active')));
    });
  });
  tabs.forEach(function (tab) {
    observer.observe(tab, { attributes: true, attributeFilter: ['class'] });
  });
})();

/*
 * "Stwórz konto" in the checkout customer form (checkout/_partials/customer-form.tpl, issue #44).
 * custom.css shows the password only while the box is ticked; here the field is also disabled while
 * hidden, so the browser does not send it and the order goes on as a guest, and required once shown.
 */
(function () {
  var box = document.getElementById('ciocia-create-account');
  var field = document.querySelector('#ciocia-account-password input[name="password"]');
  if (!box || !field) return;
  function sync() {
    field.disabled = !box.checked;
    field.required = box.checked;
  }
  box.addEventListener('change', sync);
  sync();
})();

/*
 * "Kupuję na firmę" in the address step (checkout/_partials/address-form.tpl, issue #44), as on the
 * source. Ticked, the form is the company's invoice address with NIP / VAT UE; clearing "Użyj tego adresu
 * także do dostawy" opens a second address for delivery, built here from a copy of the fields, without
 * names so the browser never sends it with the form.
 * PrestaShop saves one address per request and the delivery address first (CheckoutAddressesStep), so
 * with two addresses "Dalej" does what Classic's two forms would do:
 * 1. sends the delivery address in the background, as Classic's delivery form without use_same_address.
 *    PrestaShop answers with its invoice form and the new address chosen in the delivery list;
 * 2. sends this form as that invoice form (saveAddress=invoice, the delivery address id and
 *    confirm-addresses), which completes the step.
 * Errors from 1 are shown under the copied fields. Errors from 2 come back on Classic's invoice form,
 * with the delivery address already saved, so nothing is saved twice.
 */
(function () {
  var company = document.getElementById('ciocia-company');
  if (!company) return;
  var form = company.form;
  var same = form.querySelector('#use_same_address');
  var vat = form.querySelector('[name="vat_number"]');
  var fields = form.querySelector('.ciocia-address-fields');
  var submitButton = form.querySelector('button[name="confirm-addresses"]');
  if (!same || !fields || !submitButton) return;

  var section = document.createElement('div');
  section.className = 'ciocia-delivery-section';
  var heading = document.createElement('h2');
  heading.className = 'ciocia-address-heading';
  heading.textContent = fields.dataset.deliveryHeading;
  var errorBox = document.createElement('div');
  errorBox.className = 'alert alert-danger ciocia-delivery-error';
  errorBox.setAttribute('role', 'alert');
  errorBox.tabIndex = -1;
  errorBox.hidden = true;
  var copy = fields.cloneNode(true);
  copy.querySelectorAll('.ciocia-vat-field').forEach(function (element) {
    element.remove();
  });
  var copiedFields = copy.querySelectorAll('input, select');
  copiedFields.forEach(function (field) {
    var id = 'ciocia-delivery-' + field.name;
    var label = copy.querySelector('label[for="' + field.id + '"]');
    if (label) label.htmlFor = id;
    field.dataset.name = field.name;
    field.removeAttribute('name');
    field.id = id;
    // Classic reloads the whole address form when a .js-country select changes
    field.classList.remove('js-country');
  });
  section.append(heading, errorBox, copy);
  same.closest('.ciocia-same-address').after(section);

  function sync() {
    if (!company.checked) same.checked = true;
    if (vat) vat.disabled = !company.checked;
    var separate = company.checked && !same.checked;
    section.hidden = !separate;
    copiedFields.forEach(function (field) {
      field.disabled = !separate;
    });
  }
  company.addEventListener('change', sync);
  same.addEventListener('change', sync);
  sync();

  function clearErrors() {
    errorBox.hidden = true;
    errorBox.textContent = '';
    copy.querySelectorAll('.ciocia-field-error').forEach(function (note) {
      note.remove();
    });
    copiedFields.forEach(function (field) {
      field.removeAttribute('aria-invalid');
      field.removeAttribute('aria-describedby');
      field.closest('.form-group').classList.remove('has-error');
    });
  }

  // Errors as Classic prints them (form-errors.tpl), taken from PrestaShop's answer to request 1
  function showErrors(page) {
    var general = [];
    var firstField = null;
    if (page) {
      page.querySelectorAll('#delivery-address .form-group').forEach(function (group) {
        var source = group.querySelector('[name]');
        var messages = Array.from(group.querySelectorAll('.help-block li'), function (item) {
          return item.textContent.trim();
        });
        if (!source || !messages.length) return;
        var field = copy.querySelector('[data-name="' + source.getAttribute('name') + '"]');
        if (!field) {
          general = general.concat(messages);
          return;
        }
        var note = document.createElement('div');
        note.className = 'help-block ciocia-field-error';
        note.id = field.id + '-error';
        var list = document.createElement('ul');
        messages.forEach(function (message) {
          var item = document.createElement('li');
          item.className = 'alert alert-danger';
          item.textContent = message;
          list.append(item);
        });
        note.append(list);
        field.closest('.js-input-column').append(note);
        field.closest('.form-group').classList.add('has-error');
        field.setAttribute('aria-invalid', 'true');
        field.setAttribute('aria-describedby', note.id);
        firstField = firstField || field;
      });
      page.querySelectorAll('#delivery-address .js-address-form > .help-block li, #notifications .alert-danger li').forEach(function (item) {
        general.push(item.textContent.trim());
      });
    }
    if (!firstField && !general.length) general.push('Nie udało się zapisać adresu dostawy. Spróbuj ponownie.');
    if (general.length) {
      errorBox.textContent = general.join(' ');
      errorBox.hidden = false;
    }
    (firstField || errorBox).focus();
  }

  function addHidden(name, value) {
    var input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    form.append(input);
  }

  var sending = false;
  form.addEventListener('submit', function (event) {
    if (!company.checked || same.checked) return;
    event.preventDefault();
    if (sending) return;
    clearErrors();

    var body = new FormData();
    form.querySelectorAll('input[type="hidden"][name="token"], input[type="hidden"][name="back"]').forEach(function (input) {
      body.append(input.name, input.value);
    });
    copiedFields.forEach(function (field) {
      body.append(field.dataset.name, field.value);
    });
    body.append('saveAddress', 'delivery');
    body.append('submitAddress', '1');

    sending = true;
    submitButton.disabled = true;
    fetch(form.action, { method: 'POST', body: body, credentials: 'same-origin' })
      .then(function (response) {
        return response.text();
      })
      .then(function (html) {
        var page = new DOMParser().parseFromString(html, 'text/html');
        var delivery = page.querySelector('#invoice-address') &&
          page.querySelector('#delivery-addresses input[name="id_address_delivery"][checked]');
        if (!delivery) {
          showErrors(page);
          return false;
        }
        form.querySelector('input[name="saveAddress"]').value = 'invoice';
        addHidden('id_address_delivery', delivery.value);
        addHidden('confirm-addresses', '1');
        // The prototype's submit sends the form without running this handler again
        HTMLFormElement.prototype.submit.call(form);
        return true;
      })
      .catch(function () {
        showErrors(null);
        return false;
      })
      .then(function (sent) {
        if (sent) return;
        sending = false;
        submitButton.disabled = false;
      });
  });
})();
