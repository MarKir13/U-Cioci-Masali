{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
<section class="ciocia-trust" aria-label="Dlaczego warto u nas kupować">
  <div class="container">
    <ul class="ciocia-trust-list">
      <li><i class="material-icons" aria-hidden="true">flight</i>Naturalne i oryginalne produkty z Indii</li>
      <li><i class="material-icons" aria-hidden="true">local_shipping</i>Szybka wysyłka w 24h</li>
      <li><i class="material-icons" aria-hidden="true">group</i>Sprawdź opinie naszych klientów</li>
      <li><i class="material-icons" aria-hidden="true">lock</i>Bezpieczne płatności, szyfrowane transakcje</li>
      <li><i class="material-icons" aria-hidden="true">emoji_events</i>16 lat doświadczenia w branży Ajurwedy</li>
    </ul>
  </div>
</section>

<div class="ciocia-footer-before">
  <div class="container">
    {block name='hook_footer_before'}
      {hook h='displayFooterBefore'}
    {/block}
  </div>
</div>

<div class="ciocia-footer-main">
  <div class="container">
    <div class="ciocia-footer-columns">
      {block name='hook_footer'}
        {hook h='displayFooter'}
      {/block}
    </div>
    {block name='hook_footer_after'}
      {hook h='displayFooterAfter'}
    {/block}
    {block name='copyright_link'}
      <p class="ciocia-copyright">
        &copy; Copyright {$smarty.now|date_format:'Y'} <strong>U Cioci Masali</strong> &mdash; Wszelkie prawa zastrzeżone
      </p>
    {/block}
  </div>
</div>
