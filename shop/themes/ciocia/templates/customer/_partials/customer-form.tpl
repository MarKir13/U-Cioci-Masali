{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{* As on the source: no title (Pan/Pani), birth date or partner offers on the registration form. None is required, so the form still validates. The terms, data-processing and newsletter checkboxes stay. *}
{extends file='parent:customer/_partials/customer-form.tpl'}

{block "form_fields"}
  {$smarty.block.parent}
  {* Registration only: the consents come last, in the order of the source: terms, data notice, newsletter. *}
  {if $page.page_name === 'registration'}
    {foreach from=['psgdpr', 'customer_privacy', 'newsletter'] item='ciocia_name'}
      {foreach from=$formFields item='field'}
        {if $field.name === $ciocia_name}
          {form_field field=$field}
        {/if}
      {/foreach}
    {/foreach}
  {/if}
{/block}

{block "form_field"}
  {if $page.page_name === 'registration' && ($field.name === 'psgdpr' || $field.name === 'customer_privacy' || $field.name === 'newsletter')}
    {* Printed after the other fields, see form_fields above. *}
  {elseif $field.name === 'id_gender' || $field.name === 'birthday' || $field.name === 'optin'}
    {* Not asked, see above. *}
  {elseif $field.type === 'password'}
    <div class="field-password-policy">
      {form_field field=$field}
    </div>
  {else}
    {form_field field=$field}
  {/if}
{/block}

{* The registration button says "Utwórz konto", as on the source; the account data page (logged in) keeps "Zapisz". *}
{block "form_buttons"}
  <button class="btn btn-primary form-control-submit float-xs-right" data-link-action="save-customer" type="submit">
    {if $customer.is_logged && !$customer.is_guest}{l s='Save' d='Shop.Theme.Actions'}{else}Utwórz konto{/if}
  </button>
{/block}
