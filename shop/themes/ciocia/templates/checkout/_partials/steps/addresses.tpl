{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Address step (issue #44), as on the source. Changed from Classic:
 * - no note that one address serves for both delivery and invoice (the form says it with its checkbox);
 * - "+ Dodaj nowy adres" as an outline button, with a capital letter;
 * - with saved addresses, "Przejdź do dostawy" instead of "Dalej" (the form keeps "Dalej", as on the source);
 * - the headings use .ciocia-address-heading, like "Adres dostawy" in the form.
 * Everything Classic's scripts use (the radios, .js-address-selector, .js-address-error, the hidden
 * #not-valid-addresses, the link that opens the invoice address) is unchanged. The cards are in custom.css.
 *}
{extends file='parent:checkout/_partials/steps/addresses.tpl'}

{block name='step_content'}
  <div class="js-address-form">
    <form
      method="POST"
      data-id-address="{$id_address}"
      action="{url entity='order' params=['id_address' => $id_address]}"
      data-refresh-url="{url entity='order' params=['ajax' => 1, 'action' => 'addressForm']}"
    >

      {if !$use_same_address}
        <h2 class="ciocia-address-heading">{l s='Shipping Address' d='Shop.Theme.Checkout'}</h2>
      {/if}

      {if $show_delivery_address_form}
        <div id="delivery-address">
          {render file                      = 'checkout/_partials/address-form.tpl'
            ui                        = $address_form
            use_same_address          = $use_same_address
            type                      = "delivery"
            form_has_continue_button  = $form_has_continue_button
          }
        </div>
      {elseif $customer.addresses|count > 0}
        <div id="delivery-addresses" class="address-selector js-address-selector">
          {include  file        = 'checkout/_partials/address-selector-block.tpl'
            addresses   = $customer.addresses
            name        = "id_address_delivery"
            selected    = $id_address_delivery
            type        = "delivery"
            interactive = !$show_delivery_address_form and !$show_invoice_address_form
          }
        </div>

        {if isset($delivery_address_error)}
          <p class="alert alert-danger js-address-error" name="alert-delivery" id="id-failure-address-{$delivery_address_error.id_address}">{$delivery_address_error.exception}</p>
        {else}
          <p class="alert alert-danger js-address-error" name="alert-delivery" style="display: none">{l s="Your address is incomplete, please update it." d="Shop.Notifications.Error"}</p>
        {/if}

        <p class="add-address">
          <a class="btn btn-outline-primary ciocia-add-address" href="{$new_address_delivery_url}"><i class="material-icons" aria-hidden="true">&#xE145;</i>Dodaj nowy adres</a>
        </p>

        {if $use_same_address && !$cart.is_virtual}
          <p class="ciocia-invoice-link">
            <a data-link-action="different-invoice-address" href="{$use_different_address_url}">
              {l s='Billing address differs from shipping address' d='Shop.Theme.Checkout'}
            </a>
          </p>
        {/if}

      {/if}

      {if !$use_same_address}

        <h2 class="ciocia-address-heading">{l s='Your Invoice Address' d='Shop.Theme.Checkout'}</h2>

        {if $show_invoice_address_form}
          <div id="invoice-address">
            {render file                      = 'checkout/_partials/address-form.tpl'
              ui                        = $address_form
              use_same_address          = $use_same_address
              type                      = "invoice"
              form_has_continue_button  = $form_has_continue_button
            }
          </div>
        {else}
          <div id="invoice-addresses" class="address-selector js-address-selector">
            {include  file        = 'checkout/_partials/address-selector-block.tpl'
              addresses   = $customer.addresses
              name        = "id_address_invoice"
              selected    = $id_address_invoice
              type        = "invoice"
              interactive = !$show_delivery_address_form and !$show_invoice_address_form
            }
          </div>

          {if isset($invoice_address_error)}
            <p class="alert alert-danger js-address-error" name="alert-invoice" id="id-failure-address-{$invoice_address_error.id_address}">{$invoice_address_error.exception}</p>
          {else}
            <p class="alert alert-danger js-address-error" name="alert-invoice" style="display: none">{l s="Your address is incomplete, please update it." d="Shop.Notifications.Error"}</p>
          {/if}

          <p class="add-address">
            <a class="btn btn-outline-primary ciocia-add-address" href="{$new_address_invoice_url}"><i class="material-icons" aria-hidden="true">&#xE145;</i>Dodaj nowy adres</a>
          </p>
        {/if}

      {/if}

      {if !$form_has_continue_button}
        <div class="clearfix">
          <button type="submit" class="btn btn-primary continue float-xs-right" name="confirm-addresses" value="1">
            Przejdź do dostawy
          </button>
          <input type="hidden" id="not-valid-addresses" class="js-not-valid-addresses" value="{$not_valid_addresses}">
        </div>
      {/if}

    </form>
    {hook h='displayAddressSelectorBottom'}
  </div>
{/block}
