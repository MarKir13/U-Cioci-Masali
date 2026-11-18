{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Address form in the checkout (issue #44), as on the source: the fields in the order Kraj, NIP / VAT UE,
 * Firma, Imię, Nazwisko, Adres, Kod pocztowy, Miasto, Telefon. Left out: "Uzupełnienie adresu" and the
 * alias (PrestaShop fills in "Mój adres"). Neither is required.
 *
 * For the first address of a customer the form starts with "Kupuję na firmę":
 * - clear: the form is the delivery address, also used for the invoice (use_same_address stays ticked);
 * - ticked: NIP / VAT UE opens, and "Użyj tego adresu także do dostawy" appears under the fields.
 *   Clearing that box opens a second address, the delivery one, built by custom.js from these fields.
 *   PrestaShop saves one address per request and always the delivery address first, so custom.js saves
 *   the second address as the delivery address in the background, then sends this form as the invoice
 *   address. How each part is shown is in custom.css.
 * Other address forms (a second address of a registered customer, the invoice form) keep Classic's
 * "Użyj tego adresu także do faktury".
 *}
{extends file='parent:checkout/_partials/address-form.tpl'}

{* The whole fields section: Classic's form_fields block is "append", so overriding it would keep its loop. *}
{block name='address_form_fields'}
<section class="form-fields">
  {assign var='ciocia_company_form' value=($type === 'delivery' && $customer.addresses|count == 0)}

  {assign var='ciocia_vat_number' value=''}
  {foreach from=$formFields item='field'}
    {if $field.type === 'hidden'}
      {form_field field=$field}
    {elseif $field.name === 'vat_number'}
      {assign var='ciocia_vat_number' value=$field.value}
    {/if}
  {/foreach}

  {if $ciocia_company_form}
    <div class="form-group ciocia-company-toggle">
      <span class="custom-checkbox">
        <label>
          <input type="checkbox" id="ciocia-company"{if $ciocia_vat_number} checked{/if}>
          <span><i class="material-icons rtl-no-flip checkbox-checked">&#xE5CA;</i></span>
          Kupuję na firmę
        </label>
      </span>
    </div>
    <h2 class="ciocia-address-heading">{l s='Shipping Address' d='Shop.Theme.Checkout'}</h2>
  {/if}

  <div class="ciocia-address-fields" data-delivery-heading="{l s='Shipping Address' d='Shop.Theme.Checkout'}">
    {foreach from=['id_country', 'vat_number', 'company', 'firstname', 'lastname', 'address1', 'postcode', 'city', 'phone'] item='name'}
      {foreach from=$formFields item='field'}
        {if $field.name === $name}
          {if $name === 'vat_number'}
            {$field.label = 'NIP / VAT UE'}
            <div class="ciocia-vat-field">{form_field field=$field}</div>
          {else}
            {form_field field=$field}
          {/if}
        {/if}
      {/foreach}
    {/foreach}

    {* Fields of other countries' formats (state, DNI, second phone), none of them used in Poland. *}
    {foreach from=$formFields item='field'}
      {if $field.type !== 'hidden' && $field.name !== 'alias' && $field.name !== 'address2' && $field.name !== 'id_country' && $field.name !== 'vat_number' && $field.name !== 'company' && $field.name !== 'firstname' && $field.name !== 'lastname' && $field.name !== 'address1' && $field.name !== 'postcode' && $field.name !== 'city' && $field.name !== 'phone'}
        {form_field field=$field}
      {/if}
    {/foreach}
  </div>

  <input type="hidden" name="saveAddress" value="{$type}">
  {if $type === 'delivery'}
    <div class="form-group ciocia-same-address">
      <span class="custom-checkbox">
        <label>
          <input name="use_same_address" id="use_same_address" type="checkbox" value="1"{if $use_same_address} checked{/if}>
          <span><i class="material-icons rtl-no-flip checkbox-checked">&#xE5CA;</i></span>
          {if $ciocia_company_form}
            Użyj tego adresu także do dostawy
          {else}
            {l s='Use this address for invoice too' d='Shop.Theme.Checkout'}
          {/if}
        </label>
      </span>
    </div>
  {/if}
</section>
{/block}
