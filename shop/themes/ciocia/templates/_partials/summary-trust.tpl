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
      <span class="ciocia-summary-trust__icon" aria-hidden="true"><i class="material-icons">lock</i></span>
      <span>
        <span class="ciocia-summary-trust__title">Bezpieczne zakupy</span>
        <span class="ciocia-summary-trust__text">Szyfrowane połączenie HTTPS</span>
      </span>
    </li>
    <li>
      <span class="ciocia-summary-trust__icon" aria-hidden="true"><i class="material-icons">local_shipping</i></span>
      <span>
        <span class="ciocia-summary-trust__title">Wysyłka tego samego dnia</span>
        <span class="ciocia-summary-trust__text">Dostawa od {$ciocia_free_shipping} zł gratis</span>
      </span>
    </li>
    <li>
      <span class="ciocia-summary-trust__icon" aria-hidden="true"><i class="material-icons">assignment_return</i></span>
      <span>
        <span class="ciocia-summary-trust__title">14 dni na zwrot</span>
        <span class="ciocia-summary-trust__text">Bez podawania przyczyny</span>
      </span>
    </li>
  </ul>
</section>
