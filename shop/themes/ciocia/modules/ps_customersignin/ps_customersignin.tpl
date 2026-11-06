{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
<div id="_desktop_user_info">
  <div class="user-info">
    {if $logged}
      <a class="account" href="{$urls.pages.my_account|escape:'htmlall':'UTF-8'}" rel="nofollow"
         aria-label="{l s='View my customer account' d='Shop.Theme.Customeraccount'}">
        <i class="material-icons" aria-hidden="true">account_circle</i>
      </a>
    {else}
      <a href="{$urls.pages.authentication|escape:'htmlall':'UTF-8'}?back={$urls.current_url|urlencode}" rel="nofollow"
         aria-label="{l s='Log in to your customer account' d='Shop.Theme.Customeraccount'}">
        <i class="material-icons" aria-hidden="true">account_circle</i>
      </a>
    {/if}
  </div>
</div>
