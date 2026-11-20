<section class="ciocia-home-about" aria-labelledby="ciocia-home-about-title">
  <div class="ciocia-home-about__intro">
    <p class="ciocia-home-section__eyebrow">Autentyczność od początku</p>
    <h2 id="ciocia-home-about-title" class="ciocia-home-about__title">Nasza historia</h2>
    <p class="ciocia-home-about__text">
      Te zdjęcia pokazują nasz dawny sklep stacjonarny - miejsce stworzone z miłości do Indii, naturalnych zapachów i ajurwedyjskiej tradycji. Dziś tę samą staranność przenosimy do sklepu online.
    </p>
    <p class="ciocia-home-about__text">
      Zapewniamy <strong>darmową dostawę od {$ciocia_free_shipping} zł</strong>, szybką realizację zamówień oraz bezpieczne płatności.
    </p>
  </div>
  {if $ciocia_gallery}
    <div class="ciocia-home-about__gallery">
      {foreach from=$ciocia_gallery item=photo name=photos}
        <img class="ciocia-home-about__photo" src="{$photo}" alt="Dawny sklep stacjonarny Magiczne Indie" width="440" height="330" loading="lazy">
      {/foreach}
    </div>
  {/if}
  <aside class="ciocia-home-about__contact">
    <h3 class="ciocia-home-about__contact-title">Kontakt</h3>
    <ul class="ciocia-home-about__contact-list">
      <li><strong>SMS:</strong> <a href="tel:+48794265385">+48 794 265 385</a> (pon–pt 8:00–15:00)</li>
      <li><strong>Email:</strong> <a href="mailto:{$ciocia_email}">{$ciocia_email}</a></li>
      <li><strong>Adres korespondencyjny:</strong> ul. Szkolna 42, 05-077 Zakręt / Warszawa-Wesoła</li>
    </ul>
    <p class="ciocia-home-about__contact-note">Godziny kontaktu: poniedziałek – piątek 8:00–15:00</p>
  </aside>
</section>
