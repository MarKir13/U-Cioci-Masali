{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{*
 * Password reset request in the narrow card, like the login page: label above a full-width field and
 * one submit button. Classic puts label, field and button in one row, with a second, shorter button
 * for phones.
 *}
{extends file='page.tpl'}

{block name='page_title'}
  {l s='Forgot your password?' d='Shop.Theme.Customeraccount'}
{/block}

{block name='page_content'}
  <form action="{$urls.pages.password}" class="forgotten-password" method="post">

    {if $errors}
      <div class="alert alert-danger" role="alert">
        <ul class="mb-0">
          {foreach $errors as $error}
            <li>{$error}</li>
          {/foreach}
        </ul>
      </div>
    {/if}

    <p class="send-renew-password-link">{l s='Please enter the email address you used to register. You will receive a temporary link to reset your password.' d='Shop.Theme.Customeraccount'}</p>

    <section class="form-fields">
      <div class="form-group row">
        <label class="col-md-3 form-control-label required" for="email">{l s='Email address' d='Shop.Forms.Labels'}</label>
        <div class="col-md-6 js-input-column">
          <input type="email" name="email" id="email" autocomplete="email" value="{if isset($smarty.post.email)}{$smarty.post.email|stripslashes}{/if}" class="form-control" required>
        </div>
      </div>
    </section>

    <footer class="form-footer ciocia-login-actions">
      <a id="back-to-login" href="{$urls.pages.authentication}" class="btn btn-outline-primary">
        {l s='Back to login' d='Shop.Theme.Actions'}
      </a>
      <button id="send-reset-link" class="form-control-submit btn btn-primary" name="submit" type="submit">
        {l s='Send reset link' d='Shop.Theme.Actions'}
      </button>
    </footer>

  </form>
{/block}

{block name='page_footer'}{/block}
