{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{* Registration page as on the source: "Masz już konto? Zaloguj się" sits under the form, after a rule. *}
{extends file='page.tpl'}

{block name='page_title'}
  Stwórz konto
{/block}

{block name='page_content'}
  {block name='register_form_container'}
    {$hook_create_account_top nofilter}
    <section class="register-form">
      {render file='customer/_partials/customer-form.tpl' ui=$register_form}
    </section>
    <hr>
    <p class="ciocia-have-account">
      Masz już konto? <a href="{$urls.pages.authentication}">Zaloguj się</a>
    </p>
  {/block}
{/block}
