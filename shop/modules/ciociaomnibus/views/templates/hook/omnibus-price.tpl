{* Omnibus line (issue #72), styled in the child theme: .omnibus-price in themes/ciocia/assets/css/custom.css *}
{if $omnibus_short}
  {* Product cards, as on the source: the price before the promotion with the promotion's end date (#111), and the
     lowest price of the 30 days before it *}
  <p class="omnibus-price omnibus-price--card">
    <span class="omnibus-line omnibus-line--before">Cena przed: <span class="omnibus-price-amount">{$omnibus_regular|escape:'html':'UTF-8'}</span>{if $omnibus_until} <span class="omnibus-sep" aria-hidden="true">·</span> do <span class="omnibus-price-amount">{$omnibus_until|escape:'html':'UTF-8'}</span>{/if}</span>
    <span class="omnibus-line omnibus-line--lowest">Najniższa 30 dni: <span class="omnibus-price-amount">{$omnibus_price|escape:'html':'UTF-8'}</span></span>
  </p>
{else}
  <p class="omnibus-before">
    Cena bezpośrednio przed obniżką: <strong>{$omnibus_regular|escape:'html':'UTF-8'}</strong>{if $omnibus_percent} <strong class="omnibus-percent">{$omnibus_percent|escape:'html':'UTF-8'}</strong>{/if}
  </p>
  {if $omnibus_until}
    <p class="omnibus-until">Promocja ważna do: <strong>{$omnibus_until|escape:'html':'UTF-8'}</strong></p>
  {/if}
  <p class="omnibus-price">
    Najniższa cena z 30 dni przed obniżką: <span class="omnibus-price-amount">{$omnibus_price|escape:'html':'UTF-8'}</span>
  </p>
{/if}
