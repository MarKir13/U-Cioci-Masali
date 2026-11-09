{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
<nav id="block_myaccount_infos" class="ciocia-footer-block" aria-labelledby="ciocia-footer-title-account">
  <p class="ciocia-footer-title" id="ciocia-footer-title-account">
    <a href="{$urls.pages.my_account}" rel="nofollow">{l s='Your account' d='Shop.Theme.Customeraccount'}</a>
    <button class="ciocia-footer-toggle collapsed" type="button" data-toggle="collapse"
            data-target="#footer_account_list" aria-controls="footer_account_list"
            aria-expanded="false" aria-labelledby="ciocia-footer-title-account">
      <i class="material-icons" aria-hidden="true">expand_more</i>
    </button>
  </p>
  <ul id="footer_account_list" class="ciocia-footer-list account-list collapse">
    {if $customer.is_logged}
      <li><a href="{$urls.pages.identity}" rel="nofollow">{l s='Information' d='Shop.Theme.Customeraccount'}</a></li>
      {if $customer.addresses|count}
        <li><a href="{$urls.pages.addresses}" rel="nofollow">{l s='Addresses' d='Shop.Theme.Customeraccount'}</a></li>
      {else}
        <li><a href="{$urls.pages.address}" rel="nofollow">{l s='Add first address' d='Shop.Theme.Customeraccount'}</a></li>
      {/if}
      {if !$configuration.is_catalog}
        <li><a href="{$urls.pages.history}" rel="nofollow">{l s='Orders' d='Shop.Theme.Customeraccount'}</a></li>
        <li><a href="{$urls.pages.order_slip}" rel="nofollow">{l s='Credit slips' d='Shop.Theme.Customeraccount'}</a></li>
      {/if}
      {if $configuration.voucher_enabled && !$configuration.is_catalog}
        <li><a href="{$urls.pages.discount}" rel="nofollow">{l s='Vouchers' d='Shop.Theme.Customeraccount'}</a></li>
      {/if}
      {if $configuration.return_enabled && !$configuration.is_catalog}
        <li><a href="{$urls.pages.order_follow}" rel="nofollow">{l s='Merchandise returns' d='Shop.Theme.Customeraccount'}</a></li>
      {/if}
      {hook h='displayMyAccountBlock'}
      <li><a href="{$urls.actions.logout}" rel="nofollow">{l s='Sign out' d='Shop.Theme.Actions'}</a></li>
    {else}
      <li><a href="{$urls.pages.guest_tracking}" rel="nofollow">{l s='Order tracking' d='Shop.Theme.Customeraccount'}</a></li>
      <li><a href="{$urls.pages.my_account}" rel="nofollow">{l s='Sign in' d='Shop.Theme.Actions'}</a></li>
      <li><a href="{$urls.pages.register}" rel="nofollow">{l s='Create account' d='Shop.Theme.Customeraccount'}</a></li>
      {hook h='displayMyAccountBlock'}
    {/if}
  </ul>
</nav>
