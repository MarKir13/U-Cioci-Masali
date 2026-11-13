{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{*
 * Login form as on the source: "Nie pamiętasz hasła?" is an outline button in one row with the submit
 * button. Checkout reuses this form (checkout/_partials/login-form.tpl replaces the form_buttons
 * block with "Dalej"), so the block names stay as in Classic.
 *}
{block name='login_form'}

  {block name='login_form_errors'}
    {include file='_partials/form-errors.tpl' errors=$errors['']}
  {/block}

  <form id="login-form" action="{block name='login_form_actionurl'}{$action}{/block}" method="post">

    <div>
      {block name='login_form_fields'}
        {foreach from=$formFields item="field"}
          {block name='form_field'}
            {form_field field=$field}
          {/block}
        {/foreach}
      {/block}
    </div>

    {block name='login_form_footer'}
      <footer class="form-footer ciocia-login-actions">
        <input type="hidden" name="submitLogin" value="1">
        <a class="btn btn-outline-primary ciocia-forgot-password" href="{$urls.pages.password}" rel="nofollow">
          {l s='Forgot your password?' d='Shop.Theme.Customeraccount'}
        </a>
        {block name='form_buttons'}
          <button id="submit-login" class="btn btn-primary" data-link-action="sign-in" type="submit">
            {l s='Sign in' d='Shop.Theme.Actions'}
          </button>
        {/block}
      </footer>
    {/block}

  </form>
{/block}
