{**
 * Delivery step (issue #44): Classic's step with each carrier as a card, as on the source: the
 * carrier name, the fee in burgundy and the delivery time. The whole card is the label of its radio,
 * so a click anywhere on it chooses the carrier; the radio stays native (Tab, arrow keys). The chosen
 * card gets a 2 px burgundy frame in custom.css (.delivery-option:has(input:checked)).
 * Kept for Classic's scripts (core.js, theme.js): the radio inside .delivery-option, and the
 * .js-carrier-extra-content box right after it, which opens for the chosen carrier.
 *}
{extends file='parent:checkout/_partials/steps/shipping.tpl'}

{block name='delivery_options'}
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
{/block}
