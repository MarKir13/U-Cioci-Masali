{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{* Login page as on the source: short title, and "Utwórz konto" as a full-width outline button. *}
{extends file='page.tpl'}

{block name='page_title'}
  Zaloguj się
{/block}

{block name='page_content'}
    {block name='login_form_container'}
      <section class="login-form">
        {render file='customer/_partials/login-form.tpl' ui=$login_form}
      </section>
      <hr/>
      {block name='display_after_login_form'}
        {hook h='displayCustomerLoginFormAfter'}
      {/block}
      <div class="no-account">
        <h2 class="h4">Nie masz konta?</h2>
        <a class="btn btn-outline-primary ciocia-create-account" href="{$urls.pages.register}" data-link-action="display-register-form">
          Utwórz konto
        </a>
      </div>
    {/block}
{/block}
