{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Customer form in the personal information step (issue #44), as on the source: first name, last name
 * and e-mail, then the checkboxes. Left out here, in the checkout only: the title (Pan/Pani), the birth
 * date, the partner offers and the newsletter. None of them is required, so the order goes through without
 * them; the registration page keeps them.
 * For a guest the password sits behind a "Stwórz konto" checkbox: it opens only when the box is ticked
 * (custom.css), and custom.js disables it while the box is clear, so an untouched form orders as a guest.
 * The box starts ticked when the server returns an error for the password, so the error stays visible.
 *}
{extends file='parent:checkout/_partials/customer-form.tpl'}

{block "form_field"}
  {if $field.name === 'id_gender' || $field.name === 'birthday' || $field.name === 'optin' || $field.name === 'newsletter'}
    {* Not asked in the checkout, see above. *}
  {elseif $field.name === 'password' && $guest_allowed}
    <div class="ciocia-create-account">
      <div class="form-group row">
        <div class="col-md-3"></div>
        <div class="col-md-6">
          <span class="custom-checkbox">
            <label>
              <input type="checkbox" id="ciocia-create-account" aria-controls="ciocia-account-password"{if $field.errors} checked{/if}>
              <span><i class="material-icons rtl-no-flip checkbox-checked">&#xE5CA;</i></span>
              <span class="ciocia-create-account__title">{l s='Create an account' d='Shop.Theme.Checkout'}</span>
              <span class="ciocia-create-account__optional">{l s='(optional)' d='Shop.Theme.Checkout'}</span><br>
              <em>{l s='And save time on your next order!' d='Shop.Theme.Checkout'}</em>
            </label>
          </span>
        </div>
      </div>
      <div class="ciocia-account-password field-password-policy" id="ciocia-account-password">
        {form_field field=$field}
      </div>
    </div>
  {elseif $field.type === 'password'}
    <div class="field-password-policy">
      {form_field field=$field}
    </div>
  {else}
    {form_field field=$field}
  {/if}
{/block}
