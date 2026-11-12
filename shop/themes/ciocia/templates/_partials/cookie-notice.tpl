{**
 * Cookie notice, laid out as on the source shop: a panel at the bottom of the window on the first
 * visit and a small "Cookies" tab in the bottom left corner after a choice, which opens it again.
 * Both start hidden; custom.js shows the right one from the choice saved in the browser.
 * The shop sets only the cookies it needs to work. The analytics and advertising options are kept
 * from the source, so the saved choice is ready if such scripts are ever added.
 *}
{assign var='ciocia_privacy_page' value=Configuration::get('CIOCIA_PRIVACY_CMS_ID')|intval}
<div id="ciocia-cookie-notice" class="ciocia-cookie" role="dialog" aria-modal="false"
  aria-labelledby="ciocia-cookie-title" aria-describedby="ciocia-cookie-text" hidden>
  <div class="ciocia-cookie__panel">
    <p id="ciocia-cookie-title" class="ciocia-cookie__title">Pliki cookies</p>
    <p id="ciocia-cookie-text" class="ciocia-cookie__text">
      Używamy niezbędnych cookies do działania sklepu: koszyka, logowania i bezpieczeństwa.
      Analityczne i reklamowe włączamy tylko za Twoją zgodą. Wybór zmienisz w każdej chwili przyciskiem „Cookies”.
      {if $ciocia_privacy_page}
        <a class="ciocia-cookie__link" href="{$link->getCMSLink($ciocia_privacy_page)|escape:'htmlall':'UTF-8'}">Polityka prywatności</a>
      {/if}
    </p>
    <div class="ciocia-cookie__actions">
      <button type="button" class="ciocia-cookie__btn ciocia-cookie__btn--primary" data-cookie-accept>Akceptuję wszystkie</button>
      <button type="button" class="ciocia-cookie__btn ciocia-cookie__btn--ghost" data-cookie-necessary>Tylko niezbędne</button>
      <button type="button" class="ciocia-cookie__btn ciocia-cookie__btn--text" data-cookie-customize
        aria-expanded="false" aria-controls="ciocia-cookie-details">Dostosuj</button>
    </div>
    <div id="ciocia-cookie-details" class="ciocia-cookie__details" hidden>
      <label class="ciocia-cookie__opt">
        <input type="checkbox" checked disabled>
        <span><strong>Niezbędne</strong> — koszyk, sesja, bezpieczeństwo. Zawsze aktywne.</span>
      </label>
      <label class="ciocia-cookie__opt">
        <input type="checkbox" data-cookie-analytics>
        <span><strong>Analityczne</strong> — statystyki odwiedzin.</span>
      </label>
      <label class="ciocia-cookie__opt">
        <input type="checkbox" data-cookie-ads>
        <span><strong>Reklamowe</strong> — remarketing i personalizacja reklam.</span>
      </label>
      <button type="button" class="ciocia-cookie__btn ciocia-cookie__btn--primary ciocia-cookie__btn--save" data-cookie-save>Zapisz wybór</button>
    </div>
  </div>
</div>
<button type="button" id="ciocia-cookie-reopen" class="ciocia-cookie-reopen" aria-label="Ustawienia cookies"
  aria-controls="ciocia-cookie-notice" hidden>Cookies</button>
