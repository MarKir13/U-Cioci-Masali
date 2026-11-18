{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Personal information step (issue #44), as on the source: a box that recommends ordering as a guest,
 * and the two tabs as "Zamówienie jako gość" / "Zaloguj się" with the active one underlined (custom.css).
 * Tabs fixed for screen readers: the list items are presentation only, Classic's "|" item is gone, every
 * tab has aria-selected (custom.js keeps it current), and the panels have no aria-hidden. Classic sets
 * aria-hidden once on the server, so after a switch the visible form stayed hidden from screen readers;
 * the inactive panel is display: none anyway.
 *}
{extends file='parent:checkout/_partials/steps/personal-information.tpl'}

{block name='step_content'}
  {hook h='displayPersonalInformationTop' customer=$customer}

  {if $customer.is_logged && !$customer.is_guest}

    <p class="identity">
      {* [1][/1] is for a HTML tag. *}
      {l s='Connected as [1]%firstname% %lastname%[/1].'
        d='Shop.Theme.Customeraccount'
        sprintf=[
          '[1]' => "<a href='{$urls.pages.identity}'>",
          '[/1]' => "</a>",
          '%firstname%' => $customer.firstname,
          '%lastname%' => $customer.lastname
        ]
      }
    </p>
    <p>
      {* [1][/1] is for a HTML tag. *}
      {l
        s='Not you? [1]Log out[/1]'
        d='Shop.Theme.Customeraccount'
        sprintf=[
        '[1]' => "<a href='{$urls.actions.logout}'>",
        '[/1]' => "</a>"
        ]
      }
    </p>
    {if !isset($empty_cart_on_logout) || $empty_cart_on_logout}
      <p><small>{l s='If you sign out now, your cart will be emptied.' d='Shop.Theme.Checkout'}</small></p>
    {/if}

    <div class="clearfix">
      <form method="GET" action="{$urls.pages.order}">
        <button
          class="continue btn btn-primary float-xs-right"
          name="controller"
          type="submit"
          value="order"
        >
          {l s='Continue' d='Shop.Theme.Actions'}
        </button>
      </form>
    </div>

  {else}
    {if $guest_allowed}
      <div class="ciocia-guest-info">
        <p class="ciocia-guest-info__title">Najszybsze zamówienie: kup jako gość</p>
        <p class="ciocia-guest-info__text">Wystarczą e-mail i adres dostawy. Założenie konta jest opcjonalne.</p>
      </div>
    {/if}

    <ul class="nav nav-inline my-2 ciocia-tabs" role="tablist">
      <li class="nav-item" role="presentation">
        <a
          class="nav-link {if !$show_login_form}active{/if}"
          id="checkout-guest-tab"
          data-toggle="tab"
          href="#checkout-guest-form"
          role="tab"
          aria-controls="checkout-guest-form"
          aria-selected="{if !$show_login_form}true{else}false{/if}"
        >
          {if $guest_allowed}
            {l s='Order as a guest' d='Shop.Theme.Checkout'}
          {else}
            {l s='Create an account' d='Shop.Theme.Customeraccount'}
          {/if}
        </a>
      </li>
      <li class="nav-item" role="presentation">
        <a
          class="nav-link {if $show_login_form}active{/if}"
          id="checkout-login-tab"
          data-link-action="show-login-form"
          data-toggle="tab"
          href="#checkout-login-form"
          role="tab"
          aria-controls="checkout-login-form"
          aria-selected="{if $show_login_form}true{else}false{/if}"
        >
          {l s='Sign in' d='Shop.Theme.Actions'}
        </a>
      </li>
    </ul>

    <div class="tab-content">
      <div class="tab-pane {if !$show_login_form}active{/if}" id="checkout-guest-form" role="tabpanel" aria-labelledby="checkout-guest-tab">
        {render file='checkout/_partials/customer-form.tpl' ui=$register_form guest_allowed=$guest_allowed}
      </div>
      <div class="tab-pane {if $show_login_form}active{/if}" id="checkout-login-form" role="tabpanel" aria-labelledby="checkout-login-tab">
        {render file='checkout/_partials/login-form.tpl' ui=$login_form}
      </div>
    </div>
  {/if}
{/block}
