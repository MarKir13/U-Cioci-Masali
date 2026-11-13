{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Delivery step (issue #44), as on the source. Changed from Classic:
 * - each carrier is a card: the name, the fee in burgundy and the delivery time. The whole card is the
 *   label of its radio, so a click anywhere on it chooses the carrier; the radio stays native (Tab, arrow
 *   keys). The chosen card gets a 2 px burgundy frame in custom.css (.delivery-option:has(input:checked));
 * - the button says "Przejdź do płatności" instead of "Dalej". It sits in Classic's step_content block
 *   with no block of its own, so the whole block is here.
 * Kept for Classic's scripts (core.js, theme.js): #js-delivery and its data-url-update, the radio inside
 * .delivery-option, the .js-carrier-extra-content box right after it (opens for the chosen carrier), the
 * gift checkbox and the button's name confirmDeliveryOption.
 *}
{extends file='parent:checkout/_partials/steps/shipping.tpl'}

{block name='step_content'}
  <div id="hook-display-before-carrier">
    {$hookDisplayBeforeCarrier nofilter}
  </div>

  <div class="delivery-options-list">
    {if $delivery_options|count}
      <form
        class="clearfix"
        id="js-delivery"
        data-url-update="{url entity='order' params=['ajax' => 1, 'action' => 'selectDeliveryOption']}"
        method="post"
      >
        <div class="form-fields">
          <div class="delivery-options">
            {foreach from=$delivery_options item=carrier key=carrier_id}
              <div class="delivery-option js-delivery-option">
                <label class="ciocia-option" for="delivery_option_{$carrier.id}">
                  <span class="custom-radio">
                    <input type="radio" name="delivery_option[{$id_address}]" id="delivery_option_{$carrier.id}" value="{$carrier_id}"{if $delivery_option == $carrier_id} checked{/if}>
                    <span></span>
                  </span>
                  <span class="ciocia-option__body">
                    {if $carrier.logo}
                      <img class="ciocia-option__logo" src="{$carrier.logo}" alt="" loading="lazy">
                    {/if}
                    <span class="ciocia-option__name carrier-name">{$carrier.name}</span>
                    <span class="ciocia-option__price carrier-price">{$carrier.price}</span>
                    <span class="ciocia-option__text carrier-delay">{$carrier.delay}</span>
                  </span>
                </label>
              </div>
              <div class="carrier-extra-content js-carrier-extra-content"{if ($delivery_option != $carrier_id) || ($delivery_option == $carrier_id && empty($carrier.extraContent))} style="display:none;"{/if}>
                {$carrier.extraContent nofilter}
              </div>
            {/foreach}
          </div>

          <div class="order-options">
            <div id="delivery">
              <label for="delivery_message">{l s='If you would like to add a comment about your order, please write it in the field below.' d='Shop.Theme.Checkout'}</label>
              <textarea rows="2" cols="120" id="delivery_message" name="delivery_message">{$delivery_message}</textarea>
            </div>

            {if $recyclablePackAllowed}
              <span class="custom-checkbox">
                <input type="checkbox" id="input_recyclable" name="recyclable" value="1" {if $recyclable} checked {/if}>
                <span><i class="material-icons rtl-no-flip checkbox-checked">&#xE5CA;</i></span>
                <label for="input_recyclable">{l s='I would like to receive my order in recycled packaging.' d='Shop.Theme.Checkout'}</label>
              </span>
            {/if}

            {if $gift.allowed}
              <span class="custom-checkbox">
                <input class="js-gift-checkbox" id="input_gift" name="gift" type="checkbox" value="1" {if $gift.isGift}checked="checked"{/if}>
                <span><i class="material-icons rtl-no-flip checkbox-checked">&#xE5CA;</i></span>
                <label for="input_gift">{$gift.label}</label >
              </span>

              <div id="gift" class="collapse{if $gift.isGift} in{/if}">
                <label for="gift_message">{l s='If you\'d like, you can add a note to the gift:' d='Shop.Theme.Checkout'}</label>
                <textarea rows="2" cols="120" id="gift_message" name="gift_message">{$gift.message}</textarea>
              </div>
            {/if}

          </div>
        </div>
        <button type="submit" class="continue btn btn-primary float-xs-right" name="confirmDeliveryOption" value="1">
          Przejdź do płatności
        </button>
      </form>
    {else}
      <p class="alert alert-danger">{l s='Unfortunately, there are no carriers available for your delivery address.' d='Shop.Theme.Checkout'}</p>
    {/if}
  </div>

  <div id="hook-display-after-carrier">
    {$hookDisplayAfterCarrier nofilter}
  </div>

  <div id="extra_carrier"></div>
{/block}
