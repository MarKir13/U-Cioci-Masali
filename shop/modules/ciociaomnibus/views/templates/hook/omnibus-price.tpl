{* Omnibus line (issue #72), styled in the child theme: .omnibus-price in themes/ciocia/assets/css/custom.css *}
{if $omnibus_short}
  {* Product cards, as on the source: the price before the promotion, and the lowest price of the 30 days before it *}
  <p class="omnibus-price omnibus-price--card">
    <span class="omnibus-line omnibus-line--before">Cena przed: <span class="omnibus-price-amount">{$omnibus_regular|escape:'html':'UTF-8'}</span></span>
    <span class="omnibus-line omnibus-line--lowest">Najniższa 30 dni: <span class="omnibus-price-amount">{$omnibus_price|escape:'html':'UTF-8'}</span></span>
  </p>
{else}
  <p class="omnibus-price">
    Najniższa cena z 30 dni przed obniżką: <span class="omnibus-price-amount">{$omnibus_price|escape:'html':'UTF-8'}</span>
  </p>
{/if}
