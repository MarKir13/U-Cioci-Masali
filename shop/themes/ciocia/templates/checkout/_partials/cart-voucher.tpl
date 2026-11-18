{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Promo code in the cart and checkout summary (issue #44): "Kod promocyjny" as a full-width row that
 * opens the form, as on the source, instead of Classic's "Have a promo code?" link and "Close" link.
 * Kept from Classic for its scripts: .cart-voucher (replaced after every cart update), #promo-code,
 * the add-voucher form, .js-error and .js-discount .code. The row avoids Classic's .promo-code-button
 * and .display-promo classes, whose handlers hide and show the old link.
 * Shown only while a cart rule exists; shop-settings.php adds one (promo_code).
 *}
{if $cart.vouchers.allowed}
  {block name='cart_voucher'}
    <div class="block-promo">
      <div class="cart-voucher js-cart-voucher">
        {if $cart.vouchers.added}
          {block name='cart_voucher_list'}
            <ul class="promo-name card-block">
              {foreach from=$cart.vouchers.added item=voucher}
                <li class="cart-summary-line">
                  <span class="label">{$voucher.name}</span>
                  <div class="float-xs-right">
                    <span>{$voucher.reduction_formatted}</span>
                    {if isset($voucher.code) && $voucher.code !== ''}
                      <a href="{$voucher.delete_url}" data-link-action="remove-voucher" aria-label="Usuń kod {$voucher.code}">
                        <i class="material-icons" aria-hidden="true">&#xE872;</i>
                      </a>
                    {/if}
                  </div>
                </li>
              {/foreach}
            </ul>
          {/block}
        {/if}

        <button type="button" class="ciocia-summary-toggle" data-toggle="collapse" data-target="#promo-code"
                aria-expanded="{if $cart.discounts|count > 0}true{else}false{/if}" aria-controls="promo-code">
          Kod promocyjny
          <i class="material-icons" aria-hidden="true">expand_more</i>
        </button>

        <div id="promo-code" class="collapse{if $cart.discounts|count > 0} in{/if}">
          <div class="promo-code">
            {block name='cart_voucher_form'}
              <form action="{$urls.pages.cart}" data-link-action="add-voucher" method="post">
                <input type="hidden" name="token" value="{$static_token}">
                <input type="hidden" name="addDiscount" value="1">
                <input class="promo-input form-control" type="text" name="discount_name" placeholder="Wpisz kod"
                       aria-label="Kod promocyjny">
                <button type="submit" class="btn btn-primary">Dodaj</button>
              </form>
            {/block}

            {block name='cart_voucher_notifications'}
              <div class="alert alert-danger js-error" role="alert">
                <i class="material-icons" aria-hidden="true">&#xE001;</i><span class="ml-1 js-error-text"></span>
              </div>
            {/block}
          </div>
        </div>

        {if $cart.discounts|count > 0}
          <p class="block-promo promo-highlighted">
            {l s='Take advantage of our exclusive offers:' d='Shop.Theme.Actions'}
          </p>
          <ul class="js-discount card-block promo-discounts">
            {foreach from=$cart.discounts item=discount}
              <li class="cart-summary-line">
                <span class="label">
                  <span class="code">{$discount.code}</span> - {$discount.name}
                </span>
              </li>
            {/foreach}
          </ul>
        {/if}
      </div>
    </div>
  {/block}
{/if}
