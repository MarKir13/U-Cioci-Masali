{**
 * Trust card under the order summary on the cart and checkout pages (issue #44), as on the source but
 * with our shop's facts: the delivery promise of the header and the "Dostawa" page, and the 14 days of
 * the "Zwrot towaru" page. No "online payments": we take bank transfer and cash on delivery only.
 * The free delivery threshold is read from the configuration, as in the header, so changing it in
 * shop-settings.php or the back office changes it here too.
 *}
{assign var='ciocia_free_shipping' value=Configuration::get('PS_SHIPPING_FREE_PRICE')|intval}
<section class="ciocia-summary-trust" aria-label="Zakupy w U Cioci Masali">
  <ul class="ciocia-summary-trust__list">
    <li>
      <span class="ciocia-summary-trust__icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="M5 8h14l1 12H4L5 8z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/><path d="M9.5 14.2l1.8 1.8 3.2-3.4"/></svg></span>
      <span>
        <span class="ciocia-summary-trust__title">Bezpieczne zakupy</span>
        <span class="ciocia-summary-trust__text">Szyfrowane połączenie HTTPS</span>
      </span>
    </li>
    <li>
      <span class="ciocia-summary-trust__icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="M8 6h8v9H8z"/><path d="M16 9h3l3 3v3h-6"/><circle cx="11" cy="17.5" r="1.7"/><circle cx="19" cy="17.5" r="1.7"/><path d="M2 9h4M3 12h3M4 15h2"/></svg></span>
      <span>
        <span class="ciocia-summary-trust__title">Wysyłka tego samego dnia</span>
        <span class="ciocia-summary-trust__text">Dostawa od {$ciocia_free_shipping} zł gratis</span>
      </span>
    </li>
    <li>
      <span class="ciocia-summary-trust__icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="M12 3l5 2.5v5L12 13l-5-2.5v-5L12 3z"/><path d="M7 5.5l5 2.5 5-2.5M12 8v5"/><path d="M3 17h4.5l3 1.5H15a1.5 1.5 0 0 0 0-3h-3"/><path d="M15 18.5l5-2.5"/></svg></span>
      <span>
        <span class="ciocia-summary-trust__title">14 dni na zwrot</span>
        <span class="ciocia-summary-trust__text">Bez podawania przyczyny</span>
      </span>
    </li>
  </ul>
</section>
