{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Saved address cards in the checkout (issue #44), as on the source: the radio and the alias, the
 * address, then "Edytuj" and "Usuń" as plain text links. Classic's icons, rule and .text-muted (a grey
 * with !important) are gone; the look is in custom.css. Classes and data-link-action stay for core.js.
 *}
{block name='address_selector_blocks'}
  {foreach $addresses as $address}
    <article
      class="js-address-item address-item{if $address.id == $selected} selected{/if}"
      id="{$name|classname}-address-{$address.id}"
    >
      <header class="h4">
        <label class="radio-block">
          <span class="custom-radio">
            <input
              type="radio"
              name="{$name}"
              value="{$address.id}"
              {if $address.id == $selected}checked{/if}
            >
            <span></span>
          </span>
          <span class="address-alias h4">{$address.alias}</span>
          <div class="address">{$address.formatted nofilter}</div>
        </label>
      </header>
      <footer class="address-footer">
        {if $interactive}
          <a
            class="edit-address"
            data-link-action="edit-address"
            href="{url entity='order' params=['id_address' => $address.id, 'editAddress' => $type, 'token' => $token]}"
          >
            {l s='Edit' d='Shop.Theme.Actions'}<span class="sr-only">: {$address.alias}</span>
          </a>
          <a
            class="delete-address"
            data-link-action="delete-address"
            href="{url entity='order' params=['id_address' => $address.id, 'deleteAddress' => true, 'token' => $token]}"
          >
            {l s='Delete' d='Shop.Theme.Actions'}<span class="sr-only">: {$address.alias}</span>
          </a>
        {/if}
      </footer>
    </article>
  {/foreach}
  {if $interactive}
    <p>
      <button class="ps-hidden-by-js form-control-submit center-block" type="submit">{l s='Save' d='Shop.Theme.Actions'}</button>
    </p>
  {/if}
{/block}
