{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{*
 * Contact page as on the source: one full-width card with the title, the store details card on the
 * left and the form on the right (stacked below 768 px, see custom.css).
 * The details come from the store settings (shop/config/shop-settings.php, written by
 * shop-content.php) and the bank transfer module, so they always match the footer and the CMS pages.
 * Phone and working hours show only when the shop has them set.
 *}
{extends file='page.tpl'}

{* Classic shows the page with a left column; the source has none, so the content takes the whole width. *}
{block name='left_column'}{/block}
{block name='right_column'}{/block}

{* Without this, the layout keeps the narrower column width next to the empty left column. *}
{block name='content_wrapper'}
  <div id="content-wrapper" class="js-content-wrapper col-xs-12">
    {hook h="displayContentWrapperTop"}
    {block name='content'}{/block}
    {hook h="displayContentWrapperBottom"}
  </div>
{/block}

{block name='page_header_container'}{/block}

{block name='page_content'}
  <div class="ciocia-contact">
    <h1 class="ciocia-contact-title">Kontakt</h1>
    <div class="ciocia-contact-layout">
      {block name='ciocia_contact_info'}
        {assign var='ciocia_bank_owner' value=Configuration::get('BANK_WIRE_OWNER')}
        {assign var='ciocia_bank_details' value=Configuration::get('BANK_WIRE_DETAILS')}
        <aside class="ciocia-contact-info" aria-labelledby="ciocia-contact-info-title">
          <h2 class="ciocia-contact-info-title" id="ciocia-contact-info-title">Biuro obsługi klienta</h2>
          <p class="ciocia-contact-info-lead">Napisz do nas - odpowiadamy w dni robocze.</p>
          <ul class="ciocia-contact-info-list">
            {if $shop.email}
              <li class="ciocia-contact-info-item">
                <span class="ciocia-contact-info-icon" aria-hidden="true"><i class="material-icons">email</i></span>
                <div>
                  <span class="ciocia-contact-info-label">E-mail</span>
                  <a class="ciocia-contact-info-value" href="mailto:{$shop.email}">{$shop.email}</a>
                </div>
              </li>
            {/if}
            {if $shop.phone}
              <li class="ciocia-contact-info-item">
                <span class="ciocia-contact-info-icon" aria-hidden="true"><i class="material-icons">phone</i></span>
                <div>
                  <span class="ciocia-contact-info-label">Telefon</span>
                  <a class="ciocia-contact-info-value" href="tel:{$shop.phone|replace:' ':''}">{$shop.phone}</a>
                </div>
              </li>
            {/if}
            <li class="ciocia-contact-info-item">
              <span class="ciocia-contact-info-icon" aria-hidden="true"><i class="material-icons">place</i></span>
              <div>
                <span class="ciocia-contact-info-label">Adres do zwrotów i korespondencji</span>
                <address class="ciocia-contact-info-value">
                  {$shop.name}<br>
                  {$shop.address.address1}<br>
                  {$shop.address.postcode} {$shop.address.city}
                </address>
                <p class="ciocia-contact-info-note">Na miejscu nie prowadzimy sprzedaży bezpośredniej.</p>
              </div>
            </li>
          </ul>
          <details class="ciocia-contact-info-details">
            <summary>Dane firmy</summary>
            <dl>
              <dt>Nazwa</dt>
              <dd>{$shop.name}</dd>
              <dt>Adres</dt>
              <dd>{$shop.address.address1}, {$shop.address.postcode} {$shop.address.city}</dd>
            </dl>
          </details>
          {if $ciocia_bank_details}
            <details class="ciocia-contact-info-details">
              <summary>Numer konta bankowego</summary>
              <dl>
                {if $ciocia_bank_owner}
                  <dt>Odbiorca</dt>
                  <dd>{$ciocia_bank_owner}</dd>
                {/if}
                <dt>Numer konta</dt>
                <dd>{$ciocia_bank_details}</dd>
              </dl>
            </details>
          {/if}
        </aside>
      {/block}
      <div class="ciocia-contact-form">
        {hook h='displayContactContent'}
      </div>
    </div>
  </div>
{/block}
