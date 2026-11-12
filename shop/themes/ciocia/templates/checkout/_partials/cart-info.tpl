{**
 * Info box under the cart list (issue #44), laid out as on the source but with our shop's facts:
 * free delivery, payment methods and ordering without an account.
 *
 * Free delivery uses the same numbers as PrestaShop when it decides that delivery is free (Cart.php):
 * the products in the cart, gross, after discounts (Cart::BOTH_WITHOUT_SHIPPING), against
 * PS_SHIPPING_FREE_PRICE converted to the cart's currency. The threshold is set in shop-settings.php
 * (free_shipping_from) or in the back office; this box follows either.
 * Included from cart-detailed.tpl, which Classic renders again after every cart change, so the
 * missing amount stays current without extra JavaScript.
 *}
{assign var='ciocia_free_from' value=Configuration::get('PS_SHIPPING_FREE_PRICE')|floatval}
{assign var='ciocia_free_from' value=Tools::convertPrice($ciocia_free_from)}
{assign var='ciocia_cart_total' value=Context::getContext()->cart->getOrderTotal(true, Cart::BOTH_WITHOUT_SHIPPING)}
{assign var='ciocia_missing' value=$ciocia_free_from - $ciocia_cart_total}
{assign var='ciocia_locale' value=Tools::getContextLocale(Context::getContext())}

<section class="ciocia-cart-info" aria-label="Dostawa i płatność">
  <ul class="ciocia-cart-info__list">
    {if $ciocia_free_from > 0}
      <li>
        <i class="material-icons" aria-hidden="true">local_shipping</i>
        <span>
          <span class="ciocia-cart-info__title">
            Darmowa dostawa od {$ciocia_locale->formatPrice($ciocia_free_from, $currency.iso_code)}
          </span>
          <span class="ciocia-cart-info__text">
            {if $ciocia_missing > 0}
              Brakuje Ci jeszcze {$ciocia_locale->formatPrice($ciocia_missing, $currency.iso_code)}.
            {else}
              Masz darmową dostawę.
            {/if}
          </span>
        </span>
      </li>
    {/if}
    <li>
      <i class="material-icons" aria-hidden="true">payments</i>
      <span>
        <span class="ciocia-cart-info__title">Płatność przelewem lub przy odbiorze</span>
        <span class="ciocia-cart-info__text">Formę płatności wybierzesz przy składaniu zamówienia.</span>
      </span>
    </li>
    {if Configuration::get('PS_GUEST_CHECKOUT_ENABLED')}
      <li>
        <i class="material-icons" aria-hidden="true">verified_user</i>
        <span>
          <span class="ciocia-cart-info__title">Zakup bez rejestracji</span>
          <span class="ciocia-cart-info__text">Zamówisz jako gość, konto jest opcjonalne.</span>
        </span>
      </li>
    {/if}
  </ul>
</section>
