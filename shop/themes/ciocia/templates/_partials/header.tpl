{**
 * Copyright since 2007 PrestaShop SA and Contributors
 * PrestaShop is an International Registered Trademark & Property of PrestaShop SA
 *
 * NOTICE OF LICENSE
 *
 * This source file is subject to the Academic Free License 3.0 (AFL-3.0)
 * that is bundled with this package in the file LICENSE.md.
 * It is also available through the world-wide-web at this URL:
 * https://opensource.org/licenses/AFL-3.0
 * If you did not receive a copy of the license and are unable to
 * obtain it through the world-wide-web, please send an email
 * to license@prestashop.com so we can send you a copy immediately.
 *
 * DISCLAIMER
 *
 * Do not edit or add to this file if you wish to upgrade PrestaShop to newer
 * versions in the future. If you wish to customize PrestaShop for your
 * needs please refer to https://devdocs.prestashop.com/ for more information.
 *
 * @author    PrestaShop SA and Contributors <contact@prestashop.com>
 * @copyright Since 2007 PrestaShop SA and Contributors
 * @license   https://opensource.org/licenses/AFL-3.0 Academic Free License 3.0 (AFL-3.0)
 *}
{block name='header_banner'}
  <div class="header-banner">
    {hook h='displayBanner'}
  </div>
{/block}

{block name='header_nav'}
  <div class="ciocia-topbar">
    <div class="container">
      <ul class="ciocia-topbar-benefits" aria-label="Informacje o sklepie">
        <li>
          <a href="{$link->getCMSLink(1)|escape:'htmlall':'UTF-8'}">
            <i class="material-icons" aria-hidden="true">local_shipping</i>
            <span class="ciocia-copy-desktop">Dostawa od 129 zł gratis</span>
            <span class="ciocia-copy-mobile">Dostawa gratis od 129 zł</span>
          </a>
        </li>
        <li>
          <i class="material-icons" aria-hidden="true">schedule</i>
          <span class="ciocia-copy-desktop">Wysyłka tego samego dnia</span>
          <span class="ciocia-copy-mobile">Wysyłka dzisiaj</span>
        </li>
        <li class="ciocia-topbar-experience">
          <i class="material-icons" aria-hidden="true">emoji_events</i>
          <span>16 lat doświadczenia w branży</span>
        </li>
      </ul>
      <div class="ciocia-topbar-tools hidden-sm-down">
        {hook h='displayNav2' mod='ps_currencyselector'}
        <a class="ciocia-contact-link" href="{$urls.pages.contact|escape:'htmlall':'UTF-8'}">
          <i class="material-icons" aria-hidden="true">phone</i>
          <span>Kontakt</span>
        </a>
      </div>
    </div>
  </div>
  <nav class="header-nav">
    <div class="container">
      <div class="row">
        <div class="hidden-md-up text-sm-center mobile">
          <div class="top-logo" id="_mobile_logo"></div>
          <div id="_mobile_search"></div>
          <div id="_mobile_user_info"></div>
          <div id="_mobile_cart"></div>
        </div>
      </div>
    </div>
  </nav>
{/block}

{block name='header_top'}
  <div class="header-top">
    <div class="container">
       <div class="row ciocia-header-layout">
        <div class="col-md-2 hidden-sm-down" id="_desktop_logo">
          <span class="ciocia-brand-scene" aria-hidden="true"></span>
          {if $page.page_name == 'index'}<h1>{/if}
            <a class="ciocia-brand-link" href="{$urls.base_url|escape:'htmlall':'UTF-8'}">
              <img class="logo img-fluid ciocia-brand-logo"
                   src="{$urls.child_img_url|escape:'htmlall':'UTF-8'}logo-magiczne-indie.svg"
                   alt="Magiczne Indie" width="182" height="150" fetchpriority="high">
            </a>
          {if $page.page_name == 'index'}</h1>{/if}
        </div>
        <div id="_desktop_search" class="hidden-sm-down">
          {* Classic moves children between matching _desktop_ / _mobile_ IDs. *}
          {hook h='displayTop' mod='ps_searchbar'}
        </div>
        <div class="ciocia-header-actions hidden-sm-down">
          <a class="ciocia-header-phone" href="tel:+48794265385">
            <i class="material-icons" aria-hidden="true">phone</i>
            <span class="ciocia-phone-copy">
              <span>+48 794 265 385</span>
              <small>pon - pt: 8:00 - 15:00</small>
            </span>
          </a>
          <div class="ciocia-header-cart">
            {hook h='displayNav2' mod='ps_shoppingcart'}
          </div>
        </div>
      </div>
      <nav class="ciocia-mobile-navigation hidden-md-up" aria-label="Nawigacja mobilna">
        <button type="button" id="menu-icon" aria-controls="mobile_top_menu_wrapper" aria-expanded="false">
          <i class="material-icons" aria-hidden="true">menu</i>
          <span>{l s='Categories' d='Shop.Theme.Catalog'}</span>
        </button>
        <a href="{$urls.pages.contact|escape:'htmlall':'UTF-8'}">
          <i class="material-icons" aria-hidden="true">phone</i>
          <span>Kontakt</span>
        </a>
      </nav>
      <div id="mobile_top_menu_wrapper" class="row hidden-md-up" style="display:none;">
        <div class="ciocia-drawer-heading">
          <div><span>Magiczne Indie</span><strong id="ciocia-menu-title">Kategorie produktów</strong></div>
          <button type="button" class="ciocia-menu-close" aria-label="Zamknij menu"><i class="material-icons" aria-hidden="true">close</i></button>
        </div>
        <div class="js-top-menu mobile" id="_mobile_top_menu"></div>
        <div class="js-top-menu-bottom">
          <div id="_mobile_currency_selector"></div>
        </div>
        <div class="ciocia-drawer-footer"><a href="{$urls.pages.contact|escape:'htmlall':'UTF-8'}"><i class="material-icons" aria-hidden="true">phone</i>Pomoc i kontakt</a></div>
      </div>
      <div class="ciocia-menu-backdrop" hidden></div>
    </div>
    <nav class="ciocia-desktop-navigation hidden-sm-down" aria-label="Kategorie produktów">
      <div class="container">
        <div class="header-top-right">
          {hook h='displayTop' excl='ps_searchbar'}
          <a class="ciocia-header-wishlist" href="{$link->getModuleLink('blockwishlist', 'lists')|escape:'htmlall':'UTF-8'}" aria-label="Ulubione"><i class="material-icons" aria-hidden="true">favorite_border</i></a>
          <div class="ciocia-header-account">
            {hook h='displayNav2' mod='ps_customersignin'}
          </div>
        </div>
      </div>
    </nav>
  </div>
  {hook h='displayNavFullWidth'}
{/block}
